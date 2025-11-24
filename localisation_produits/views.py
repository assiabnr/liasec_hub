import json
from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from dashboard.models import Session, Click, Product, ProductView


# --------- Helpers session ---------

def get_or_create_session(request):
    """
    Réutilise la logique 'Session' déjà utilisée par le chatbot / dashboard.
    Si aucune session_id n'est présente en session Django, on en crée une.
    """
    session_id = request.session.get("session_id")
    if session_id:
        session = Session.objects.filter(id=session_id).first()
        if session:
            return session

    # Nouvelle session "borne"
    user_id = request.session.get("user_id")  # ou None
    session = Session.objects.create(
        user_id=user_id,
        start_time=timezone.now(),
        device=request.META.get("HTTP_USER_AGENT", "inconnu"),
        location="Decathlon Lille Centre",
    )
    request.session["session_id"] = session.id
    return session


# --------- Vue principale ---------


PRICE_RANGES = {
    "0-10": (0, 10),
    "10-25": (10, 25),
    "25-50": (25, 50),
    "50-100": (50, 100),
    "100-250": (100, 250),
    "250-500": (250, 500),
    "500+": (500, None),
}


def home(request):
    query = (request.GET.get("q") or "").strip()
    price_key = (request.GET.get("price") or "").strip()
    sport_filter = (request.GET.get("sport") or "").strip()
    category_filter = (request.GET.get("category") or "").strip()
    page_number = request.GET.get("page") or 1

    products = Product.objects.all()

    # Recherche texte : nom, marque, sport, catégorie, référence
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(brand__icontains=query)
            | Q(sport__icontains=query)
            | Q(category__icontains=query)
            | Q(product_id__icontains=query)
        )

    # Filtre sport puis catégorie (catégorie uniquement si un sport est choisi)
    if sport_filter:
        products = products.filter(sport__iexact=sport_filter)
        if category_filter:
            products = products.filter(category__iexact=category_filter)
    else:
        # si aucun sport, on ignore la catégorie
        category_filter = ""

    # Filtre prix
    if price_key in PRICE_RANGES:
        min_p, max_p = PRICE_RANGES[price_key]
        if min_p is not None:
            products = products.filter(price__gte=min_p)
        if max_p is not None:
            products = products.filter(price__lte=max_p)

    products = products.order_by("name")

    paginator = Paginator(products, 5)
    page_obj = paginator.get_page(page_number)

    # Construction des éléments de pagination (1, ..., pages autour, ..., dernière)
    def build_pagination_items(page_obj, window=2):
        last = page_obj.paginator.num_pages
        if last <= 1:
            return []

        current = page_obj.number
        pages = {1, last}

        for num in range(current - window, current + window + 1):
            if 1 < num < last:
                pages.add(num)

        pages = sorted(pages)

        items = []
        prev = None
        for num in pages:
            if prev is not None and num - prev > 1:
                items.append("...")
            items.append(num)
            prev = num
        return items

    pagination_items = build_pagination_items(page_obj)

    # sports disponibles
    sports = (
        Product.objects.exclude(sport__isnull=True)
        .exclude(sport__exact="")
        .values_list("sport", flat=True)
        .distinct()
        .order_by("sport")
    )

    # catégories uniquement pour le sport sélectionné
    if sport_filter:
        categories = (
            Product.objects.filter(sport__iexact=sport_filter)
            .exclude(category__isnull=True)
            .exclude(category__exact="")
            .values_list("category", flat=True)
            .distinct()
            .order_by("category")
        )
    else:
        categories = []

    return render(
        request,
        "localisation_produits/home.html",
        {
            "products": page_obj.object_list,
            "page_obj": page_obj,
            "query": query,
            "price_key": price_key,
            "sports": sports,
            "categories": categories,
            "selected_sport": sport_filter,
            "selected_category": category_filter,
            "pagination_items": pagination_items,
        },
    )

# --------- API Recherche produits ---------

def search_products_api(request):
    """
    API JSON pour rechercher des produits de la BDD avec filtres :
    - q: texte à chercher (nom / marque / sport / catégorie / référence)
    - price: clé dans PRICE_RANGES (ex: '0-10', '50-100', '500+')
    - page: numéro de page (pagination)
    """
    session = get_or_create_session(request)

    q = (request.GET.get("q") or "").strip()
    price_key = (request.GET.get("price") or "").strip()
    page_number = request.GET.get("page") or 1

    products = Product.objects.filter(available=True)

    # Recherche plein-texte simple
    if q:
        products = products.filter(
            Q(name__icontains=q)
            | Q(brand__icontains=q)
            | Q(category__icontains=q)
            | Q(sport__icontains=q)
            | Q(product_id__icontains=q)
        )

    # Filtre de prix
    if price_key in PRICE_RANGES:
        min_p, max_p = PRICE_RANGES[price_key]
        try:
            if min_p is not None:
                products = products.filter(price__gte=Decimal(str(min_p)))
            if max_p is not None:
                products = products.filter(price__lte=Decimal(str(max_p)))
        except InvalidOperation:
            pass

    products = products.order_by("name")

    paginator = Paginator(products, 12)  # 12 produits par page
    page_obj = paginator.get_page(page_number)

    results = []
    for p in page_obj.object_list:
        results.append(
            {
                "id": p.id,
                "reference": p.product_id,
                "name": p.name,
                "brand": p.brand or "",
                "price": f"{p.price:.2f} €",
                "category": p.category or "",
                "sport": p.sport or "",
                "imageUrl": p.image_url or "",
                "imageUrlAlt": p.image_url_alt or "",
            }
        )

    # On logge la recherche comme un clic "page"
    Click.objects.create(
        session=session,
        product_name=None,
        page="localisation_search",
        timestamp=timezone.now(),
    )

    return JsonResponse(
        {
            "results": results,
            "page": page_obj.number,
            "num_pages": paginator.num_pages,
            "total": paginator.count,
        }
    )


# --------- API tracking clic loupe ---------

def track_product_view_api(request):
    """
    Appelée quand l'utilisateur clique sur la loupe pour voir / localiser un produit.
    - Log dans Click + ProductView
    - Permet au frontend de déclencher ensuite la carte (getPathIdFromCategory)
    """
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    session = get_or_create_session(request)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        data = request.POST

    product_id = data.get("product_id")
    source = data.get("source") or "localisation"
    zone = data.get("zone") or None

    product = get_object_or_404(Product, id=product_id)

    # 1) Click "loupe"
    Click.objects.create(
        session=session,
        product_name=product.name,
        page="localisation_loupe",
        timestamp=timezone.now(),
    )

    # 2) Vue produit pour les analyses produits du dashboard
    ProductView.objects.create(
        session=session,
        product=product,
        source=source,
        zone=zone,
    )

    return JsonResponse(
        {
            "success": True,
            "product": {
                "id": product.id,
                "reference": product.product_id,
                "name": product.name,
                "brand": product.brand or "",
                "price": f"{product.price:.2f} €",
                "category": product.category or "",
                "sport": product.sport or "",
            },
        }
    )


# --------- API tracking localisation carte ---------

def track_product_localization_api(request):
    """
    Appelée quand l'utilisateur voit effectivement la zone sur la carte.
    - Log la zone du magasin qui a été affichée
    - Permet de savoir si la localisation a été réussie
    """
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    session = get_or_create_session(request)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        data = request.POST

    product_id = data.get("product_id")
    zone = data.get("zone") or "inconnu"  # ex: "area12", "area7"
    zone_name = data.get("zone_name") or ""  # ex: "FIT HOMME"
    category = data.get("category") or ""
    sport = data.get("sport") or ""

    product = None
    product_name = data.get("product_name") or "Produit inconnu"

    if product_id:
        try:
            product = Product.objects.get(id=product_id)
            product_name = product.name
        except Product.DoesNotExist:
            pass

    # Log dans Click pour tracer l'événement de localisation
    Click.objects.create(
        session=session,
        product_name=product_name,
        page=f"localisation_carte_{zone}",
        timestamp=timezone.now(),
    )

    # Si on a un produit valide, on met à jour ou crée une ProductView avec la zone
    if product:
        # On cherche une vue récente (< 5 minutes) pour la mettre à jour
        recent_view = ProductView.objects.filter(
            session=session,
            product=product,
            viewed_at__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).order_by('-viewed_at').first()

        if recent_view:
            # Mise à jour de la zone
            recent_view.zone = zone_name or zone
            recent_view.save()
        else:
            # Création d'une nouvelle vue
            ProductView.objects.create(
                session=session,
                product=product,
                source="localisation_carte",
                zone=zone_name or zone,
            )

    return JsonResponse(
        {
            "success": True,
            "zone": zone,
            "zone_name": zone_name,
            "product_name": product_name,
        }
    )