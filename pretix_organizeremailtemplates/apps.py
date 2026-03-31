from django.utils.translation import gettext_lazy as _
from pretix.base.plugins import PluginConfig, PLUGIN_LEVEL_EVENT_ORGANIZER_HYBRID


class PluginApp(PluginConfig):
    name = 'pretix_organizeremailtemplates'
    label = 'pretix_organizeremailtemplates'
    verbose_name = _('Organizer Email Templates')

    class PretixPluginMeta:
        name = _('Organizer Email Templates')
        author = 'Phil Scott'
        description = _('Organizer-level email content template management with per-event lock/unlock')
        version = '1.1.0'
        category = 'CUSTOMIZATION'
        level = PLUGIN_LEVEL_EVENT_ORGANIZER_HYBRID
        visible = True

    def ready(self):
        from . import signals  # NOQA


default_app_config = 'pretix_organizeremailtemplates.apps.PluginApp'
