from django.apps import AppConfig


class BititecConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bititec'

    def ready(self):
        import bititec.signals
