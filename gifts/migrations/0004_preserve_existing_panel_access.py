from django.conf import settings
from django.db import migrations


def grant_existing_view_access(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    permissions = Permission.objects.filter(content_type__app_label="gifts", content_type__model="product")
    add = permissions.filter(codename="add_product").first()
    view = permissions.filter(codename="view_product").first()
    if add and view:
        for user in User.objects.filter(user_permissions=add).iterator():
            user.user_permissions.add(view)
        for group in Group.objects.filter(permissions=add).iterator():
            group.permissions.add(view)


class Migration(migrations.Migration):
    dependencies = [("gifts", "0003_alter_product_options_product_revision_and_more"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.RunPython(grant_existing_view_access, migrations.RunPython.noop)]
