import sys
from copy import copy

import django
from django.apps import AppConfig


class TrainingConfig(AppConfig):
    name = 'training'

    def ready(self):
        # Backport Django's BaseContext copy fix (#35844) for this legacy
        # Django 4.2 / MariaDB 10.4 installation running Python 3.14.
        # Remove when Django and the database are upgraded together.
        if sys.version_info >= (3, 14) and django.VERSION[:2] == (4, 2):
            from django.template.context import BaseContext

            def copy_context(self):
                duplicate = BaseContext()
                duplicate.__class__ = self.__class__
                duplicate.__dict__ = copy(self.__dict__)
                duplicate.dicts = self.dicts[:]
                return duplicate

            BaseContext.__copy__ = copy_context
