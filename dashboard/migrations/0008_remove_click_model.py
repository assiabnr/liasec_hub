from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0007_session_deleted_at_session_is_deleted"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Click",
        ),
    ]
