from __future__ import print_function, unicode_literals
from django.conf.urls import url, include
from rest_framework_bulk.routes import BulkRouter

from .views import SimpleViewSet

app_name = 'simple_app'

router = BulkRouter()
router.register('simple', SimpleViewSet, 'simple')

urlpatterns = (
    url(r'^api/', include(router.urls)),
)
