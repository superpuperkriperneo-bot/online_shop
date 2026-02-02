from rest_framework.routers import DefaultRouter
from .views import CategoriesViewSet, ProductsViewSet, OrderItemViewSet, OrderViewSet, CartViewSet, CartItemViewSet, TelegramWebhookView, LoginWithCodeView
from django.urls import path, include
from django.contrib import admin

router = DefaultRouter()

router.register(r'categories', CategoriesViewSet, basename='category')
router.register(r'products', ProductsViewSet, basename = 'products')
router.register(r'orders', OrderViewSet, basename='orders')
router.register(r'order-items', OrderItemViewSet, basename='order-items')
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'cart-items', CartItemViewSet, basename='cart-items')
urlpatterns = [
    path('admin/', admin.site.urls), # Admin panel ushın
    path('webhook/', TelegramWebhookView.as_view(), name='webhook'),
    path('login/', LoginWithCodeView.as_view(), name='login'),
    path('', include(router.urls)),
]
urlpatterns = router.urls