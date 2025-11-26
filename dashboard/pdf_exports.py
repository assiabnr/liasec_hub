"""
Module d'exportation PDF pour le dashboard LIASEC
Utilise ReportLab pour générer des rapports PDF professionnels
"""

import os
from datetime import datetime, timedelta
from io import BytesIO

from django.conf import settings
from django.db.models import Count, Avg, Q
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
    Image as RLImage
)
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from dashboard.models import (
    Session, ChatbotInteraction, ProductView, Product,
    ChatbotRecommendation
)


class PDFReport:
    """Classe de base pour générer des rapports PDF"""

    def __init__(self, title="Rapport Dashboard LIASEC"):
        self.title = title
        self.buffer = BytesIO()
        self.doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        self.styles = getSampleStyleSheet()
        self.story = []

        # Styles personnalisés
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#3B82F6'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1F2937'),
            spaceBefore=20,
            spaceAfter=12
        ))

        self.styles.add(ParagraphStyle(
            name='SubTitle',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#6B7280'),
            spaceAfter=10
        ))

    def add_header(self):
        """Ajoute l'en-tête du rapport"""
        title = Paragraph(self.title, self.styles['CustomTitle'])
        date = Paragraph(
            f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            self.styles['SubTitle']
        )
        self.story.append(title)
        self.story.append(date)
        self.story.append(Spacer(1, 0.5*cm))

    def add_section_title(self, text):
        """Ajoute un titre de section"""
        self.story.append(Spacer(1, 0.3*cm))
        self.story.append(Paragraph(text, self.styles['SectionTitle']))
        self.story.append(Spacer(1, 0.2*cm))

    def add_kpi_table(self, data):
        """
        Ajoute un tableau de KPIs
        data = [(label, value, variation), ...]
        """
        table_data = [['Métrique', 'Valeur', 'Évolution']]

        for label, value, variation in data:
            if variation is not None:
                var_text = f"+{variation}%" if variation >= 0 else f"{variation}%"
                var_color = colors.green if variation >= 0 else colors.red
            else:
                var_text = "N/A"
                var_color = colors.grey

            table_data.append([label, str(value), var_text])

        table = Table(table_data, colWidths=[8*cm, 4*cm, 3*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))

        self.story.append(table)
        self.story.append(Spacer(1, 0.5*cm))

    def add_simple_table(self, headers, data, col_widths=None):
        """Ajoute un tableau simple"""
        table_data = [headers] + data

        if col_widths is None:
            col_widths = [15*cm / len(headers)] * len(headers)

        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10B981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))

        self.story.append(table)
        self.story.append(Spacer(1, 0.5*cm))

    def generate(self):
        """Génère le PDF et retourne le buffer"""
        self.doc.build(self.story)
        self.buffer.seek(0)
        return self.buffer


def generate_dashboard_pdf():
    """Génère le PDF du dashboard principal"""
    report = PDFReport("Rapport d'Activité - Dashboard Général")
    report.add_header()

    # Période d'analyse
    today = timezone.now()
    last_7_days = today - timedelta(days=7)
    previous_7_days = last_7_days - timedelta(days=7)

    # === SESSIONS ===
    report.add_section_title("📊 Sessions")

    sessions_total = Session.objects.count()
    sessions_last_7 = Session.objects.filter(start_time__gte=last_7_days).count()
    sessions_previous_7 = Session.objects.filter(
        start_time__gte=previous_7_days, start_time__lt=last_7_days
    ).count()
    sessions_variation = round(
        ((sessions_last_7 - sessions_previous_7) / sessions_previous_7) * 100, 1
    ) if sessions_previous_7 > 0 else None

    kpi_sessions = [
        ("Total sessions", sessions_total, None),
        ("Sessions (7 derniers jours)", sessions_last_7, sessions_variation),
    ]
    report.add_kpi_table(kpi_sessions)

    # === CHATBOT ===
    report.add_section_title("🤖 Chatbot")

    interactions_total = ChatbotInteraction.objects.count()
    interactions_last_7 = ChatbotInteraction.objects.filter(created_at__gte=last_7_days).count()

    satisfaction_data = ChatbotInteraction.objects.filter(
        ask_feedback=True
    ).aggregate(
        positive=Count("id", filter=Q(satisfaction=True)),
        total=Count("id")
    )

    # Gérer les cas où les agrégations retournent None
    satisfaction_positive = satisfaction_data.get("positive") or 0
    satisfaction_total = satisfaction_data.get("total") or 0
    satisfaction_rate = round(
        (satisfaction_positive / satisfaction_total * 100), 1
    ) if satisfaction_total > 0 else 0

    kpi_chatbot = [
        ("Total interactions", interactions_total, None),
        ("Interactions (7 derniers jours)", interactions_last_7, None),
        ("Taux de satisfaction", f"{satisfaction_rate}%", None),
    ]
    report.add_kpi_table(kpi_chatbot)

    # === PRODUITS ===
    report.add_section_title("📦 Produits")

    total_views = ProductView.objects.count()
    views_chatbot = ProductView.objects.filter(source="chatbot").count()
    views_carte = ProductView.objects.filter(source="carte").count()
    views_recherche = ProductView.objects.filter(source="recherche").count()

    kpi_produits = [
        ("Total consultations", total_views, None),
        ("Depuis chatbot", views_chatbot, None),
        ("Depuis carte", views_carte, None),
        ("Depuis recherche", views_recherche, None),
    ]
    report.add_kpi_table(kpi_produits)

    # Top 5 produits
    report.add_section_title("🏆 Top 5 Produits les plus consultés")

    top_products = (
        ProductView.objects.values("product__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    if top_products:
        headers = ['Produit', 'Nombre de consultations']
        data = [[(p["product__name"] or "Produit inconnu")[:50], str(p["total"])] for p in top_products]
        report.add_simple_table(headers, data, col_widths=[12*cm, 3*cm])

    return report.generate()


def generate_sessions_pdf():
    """Génère le PDF des sessions"""
    report = PDFReport("Rapport d'Activité - Sessions")
    report.add_header()

    # Période
    today = timezone.now()
    last_7_days = today - timedelta(days=7)

    # === STATISTIQUES GÉNÉRALES ===
    report.add_section_title("📊 Vue d'ensemble")

    total_sessions = Session.objects.count()
    sessions_with_chatbot = Session.objects.filter(chatbot_interactions__isnull=False).distinct().count()
    sessions_with_products = Session.objects.filter(product_views__isnull=False).distinct().count()

    avg_duration_result = Session.objects.filter(duration__isnull=False).aggregate(
        avg=Avg("duration")
    )
    avg_duration = avg_duration_result.get("avg")

    if avg_duration:
        avg_duration_minutes = round((avg_duration.total_seconds() - 30) / 60, 1)
    else:
        avg_duration_minutes = 0

    kpi_data = [
        ("Total sessions", total_sessions, None),
        ("Sessions avec chatbot", sessions_with_chatbot, None),
        ("Sessions avec produits", sessions_with_products, None),
        ("Durée moyenne (min)", avg_duration_minutes, None),
    ]
    report.add_kpi_table(kpi_data)

    # === DERNIÈRES SESSIONS ===
    report.add_section_title("🕐 Dernières sessions")

    recent_sessions = Session.objects.order_by("-start_time")[:10]

    headers = ['ID', 'Date début', 'Durée', 'Interactions', 'Produits']
    data = []

    for session in recent_sessions:
        interactions_count = session.chatbot_interactions.count()
        products_count = session.product_views.count()

        duration_str = "N/A"
        if session.duration:
            duration_seconds = session.duration.total_seconds() - 30
            if duration_seconds > 0:
                duration_str = f"{int(duration_seconds // 60)}min"

        data.append([
            str(session.id),
            session.start_time.strftime("%d/%m %H:%M"),
            duration_str,
            str(interactions_count),
            str(products_count)
        ])

    report.add_simple_table(headers, data, col_widths=[2*cm, 3*cm, 2.5*cm, 3*cm, 3*cm])

    return report.generate()


def generate_chatbot_pdf():
    """Génère le PDF du chatbot"""
    report = PDFReport("Rapport d'Activité - Chatbot")
    report.add_header()

    # === STATISTIQUES GÉNÉRALES ===
    report.add_section_title("🤖 Vue d'ensemble")

    total_interactions = ChatbotInteraction.objects.count()

    success_data = ChatbotInteraction.objects.aggregate(
        success=Count("id", filter=Q(response_success=True)),
        total=Count("id")
    )

    # Gérer les cas où les agrégations retournent None
    success_count = success_data.get("success") or 0
    success_total = success_data.get("total") or 0
    success_rate = round(
        (success_count / success_total * 100), 1
    ) if success_total > 0 else 0

    satisfaction_data = ChatbotInteraction.objects.filter(
        ask_feedback=True
    ).aggregate(
        positive=Count("id", filter=Q(satisfaction=True)),
        total=Count("id")
    )

    # Gérer les cas où les agrégations retournent None
    satisfaction_positive = satisfaction_data.get("positive") or 0
    satisfaction_total = satisfaction_data.get("total") or 0
    satisfaction_rate = round(
        (satisfaction_positive / satisfaction_total * 100), 1
    ) if satisfaction_total > 0 else 0

    avg_response_time_result = ChatbotInteraction.objects.filter(
        response_time__isnull=False
    ).aggregate(avg=Avg("response_time"))
    avg_response_time = avg_response_time_result.get("avg") or 0

    kpi_data = [
        ("Total interactions", total_interactions, None),
        ("Taux de succès", f"{success_rate}%", None),
        ("Taux de satisfaction", f"{satisfaction_rate}%", None),
        ("Temps de réponse moyen (s)", round(avg_response_time, 2), None),
    ]
    report.add_kpi_table(kpi_data)

    # === TOP INTENTS ===
    report.add_section_title("🎯 Top Intents")

    top_intents = (
        ChatbotInteraction.objects.exclude(intent__isnull=True)
        .exclude(intent="")
        .values("intent")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )

    if top_intents:
        headers = ['Intent', 'Nombre']
        data = [[intent["intent"] or "Non défini", str(intent["total"])] for intent in top_intents]
        report.add_simple_table(headers, data, col_widths=[10*cm, 5*cm])

    # === PRODUITS RECOMMANDÉS ===
    report.add_section_title("📦 Recommandations de produits")

    total_recos = ChatbotRecommendation.objects.count()
    clicked_recos = ChatbotRecommendation.objects.filter(clicked=True).count()
    conversion_rate = round((clicked_recos / total_recos * 100), 1) if total_recos > 0 else 0

    kpi_recos = [
        ("Total recommandations", total_recos, None),
        ("Recommandations cliquées", clicked_recos, None),
        ("Taux de conversion", f"{conversion_rate}%", None),
    ]
    report.add_kpi_table(kpi_recos)

    return report.generate()


def generate_products_pdf():
    """Génère le PDF des produits"""
    report = PDFReport("Rapport d'Activité - Produits")
    report.add_header()

    # === STATISTIQUES GÉNÉRALES ===
    report.add_section_title("📦 Vue d'ensemble")

    total_products = Product.objects.count()
    available_products = Product.objects.filter(available=True).count()
    total_views = ProductView.objects.count()

    kpi_data = [
        ("Total produits", total_products, None),
        ("Produits disponibles", available_products, None),
        ("Total consultations", total_views, None),
    ]
    report.add_kpi_table(kpi_data)

    # === RÉPARTITION PAR SOURCE ===
    report.add_section_title("📊 Consultations par source")

    views_chatbot = ProductView.objects.filter(source="chatbot").count()
    views_carte = ProductView.objects.filter(source="carte").count()
    views_recherche = ProductView.objects.filter(source="recherche").count()

    pct_chatbot = round((views_chatbot / total_views * 100), 1) if total_views > 0 else 0
    pct_carte = round((views_carte / total_views * 100), 1) if total_views > 0 else 0
    pct_recherche = round((views_recherche / total_views * 100), 1) if total_views > 0 else 0

    kpi_sources = [
        ("Chatbot", f"{views_chatbot} ({pct_chatbot}%)", None),
        ("Carte", f"{views_carte} ({pct_carte}%)", None),
        ("Recherche", f"{views_recherche} ({pct_recherche}%)", None),
    ]
    report.add_kpi_table(kpi_sources)

    # === TOP 10 PRODUITS ===
    report.add_section_title("🏆 Top 10 Produits")

    top_products = (
        ProductView.objects.values("product__name", "product__brand", "product__category")
        .annotate(views=Count("id"))
        .order_by("-views")[:10]
    )

    if top_products:
        headers = ['Produit', 'Marque', 'Catégorie', 'Vues']
        data = []
        for p in top_products:
            data.append([
                p["product__name"][:30] if p["product__name"] else "—",
                p["product__brand"][:20] if p["product__brand"] else "—",
                p["product__category"][:15] if p["product__category"] else "—",
                str(p["views"])
            ])
        report.add_simple_table(headers, data, col_widths=[5*cm, 3.5*cm, 3*cm, 2.5*cm])

    return report.generate()


def generate_clicks_pdf():
    """Génère le PDF des clics/consultations"""
    report = PDFReport("Rapport d'Activité - Consultations Produits")
    report.add_header()

    # === STATISTIQUES GÉNÉRALES ===
    report.add_section_title("👁️ Vue d'ensemble")

    total_clicks = ProductView.objects.count()
    clicks_chatbot = ProductView.objects.filter(source="chatbot").count()
    clicks_carte = ProductView.objects.filter(source="carte").count()
    clicks_recherche = ProductView.objects.filter(source="recherche").count()

    pct_chatbot = round((clicks_chatbot / total_clicks * 100), 1) if total_clicks > 0 else 0
    pct_carte = round((clicks_carte / total_clicks * 100), 1) if total_clicks > 0 else 0
    pct_recherche = round((clicks_recherche / total_clicks * 100), 1) if total_clicks > 0 else 0

    kpi_data = [
        ("Total consultations", total_clicks, None),
        ("Chatbot", f"{clicks_chatbot} ({pct_chatbot}%)", None),
        ("Carte", f"{clicks_carte} ({pct_carte}%)", None),
        ("Recherche", f"{clicks_recherche} ({pct_recherche}%)", None),
    ]
    report.add_kpi_table(kpi_data)

    # === CONVERSION RECOMMANDATIONS ===
    report.add_section_title("📈 Conversion des recommandations")

    total_recommendations = ChatbotRecommendation.objects.count()
    clicked_recommendations = ChatbotRecommendation.objects.filter(clicked=True).count()
    conversion_rate = round(
        (clicked_recommendations / total_recommendations * 100), 1
    ) if total_recommendations > 0 else 0

    kpi_conversion = [
        ("Total recommandations", total_recommendations, None),
        ("Recommandations cliquées", clicked_recommendations, None),
        ("Taux de conversion", f"{conversion_rate}%", None),
    ]
    report.add_kpi_table(kpi_conversion)

    # === TOP PRODUITS CONSULTÉS ===
    report.add_section_title("🏆 Top 10 Produits consultés")

    top_products = (
        ProductView.objects.values("product__name", "source")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )

    if top_products:
        headers = ['Produit', 'Source', 'Consultations']
        data = []
        for p in top_products:
            source_emoji = {
                "chatbot": "🤖 Chatbot",
                "carte": "🗺️ Carte",
                "recherche": "🔍 Recherche"
            }.get(p["source"], p["source"])

            data.append([
                p["product__name"][:40] if p["product__name"] else "—",
                source_emoji,
                str(p["total"])
            ])
        report.add_simple_table(headers, data, col_widths=[8*cm, 4*cm, 3*cm])

    return report.generate()
