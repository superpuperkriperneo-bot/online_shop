import random
import secrets
import logging
import requests
import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.cache import cache
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from urllib import request
from django.shortcuts import render
from django.db import transaction
from rest_framework import serializers, status, generics, HTTP_HEADER_ENCODING
from .serializers import UpdatePasswordSerializer
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter
from .permissions import IsAdminOrReadOnly, IsOwnerOrAdmin
from .serializers import (CategoriesSerializer, ProductsSerializer, CustomUserSerializer, CartSerializer,
                        CartItemSerializer,OrderSerializer, OrderItemSerializer)
from .models import Categories, Products, CustomUser, Cart, CartItem, Order, OrderItem, Reviews
from django_filters.rest_framework import DjangoFilterBackend

User = get_user_model()
logging = logging.getLogger(__name__)

class CartViewSet(viewsets.ModelViewSet):
    queryset = Cart.objects.select_related('user').all()
    serializer_class = CartSerializer

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

class CartItemViewSet(viewsets.ModelViewSet):
    queryset = CartItem.objects.select_related('cart').all()
    serializer_class = CartItemSerializer
    def get_queryset(self):
        return CartItem.objects.filter(cart__user=self.request.user)
        

    def perform_create(self, serializer):
        cart, _ = Cart.objects.get_or_create(user = self.request.user)

        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']


        if product.stock < quantity:
            raise serializers.ValidationError({"detail":f"we have {product.stock} in product stock"})

        serializer.save(cart=cart)

class CategoriesViewSet(viewsets.ModelViewSet):
    queryset = Categories.objects.all()
    serializer_class = CategoriesSerializer
    permission_classes = [IsAdminOrReadOnly]
    

class ProductsViewSet(viewsets.ModelViewSet):
    queryset = Products.objects.select_related('category').all()
    serializer_class = ProductsSerializer
    # permission_classes = [IsAdmin]
    lookup_field = 'slug'
    lookup_url_kwarg = 'slug'
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    search_fields = ['name', 'description']
    filterset_fields = ['category', 'is_active']
    ordering_fields = ['created_at','price']

    def perform_create(self, serializer):
        serializer.save(admin = request.user)

    
class UpdatePasswordView(generics.UpdateAPIView):
    serializer_class = UpdatePasswordSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            if not self.object.check_password(
                serializer.data.get("old_password")):
                return Response({'old_password' : ["Incorrect old password."]},
                                status=status.HTTP_400_BAD_REQUEST)
            self.object.set_password(serializer.data.get("brand_new_password"))
            self.object.save()

            return Response({"message": "Password successfully changed"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            


class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.select_related('user').all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    def get_reviews(self):
        if Order.status == 'delivered':
            return Reviews.objects.all()

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Order.objects.all()
        return Order.objects.filter(user=user)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def checkout(self,request):
        user = request.user
        cart = Cart.objects.filter(user=user).first()

        if not cart or not cart.items.exists():
            return Response({'detail': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            order = Order.objects.create(
                user=user,
                total_price=0,
                address=user.address or "The address was not entered",
                status='pending'
            )
            total_sum = 0
            for item in cart.items.all():
                if item.product.stock < item.quantity:
                    transaction.set_rollback(True)
                    return Response ({'detail': f'Not enough stock for {item.product.name}'}, status=status.HTTP_400_BAD_REQUEST)
                
                item.product.stock -= item.quantity
                item.product.save()

                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
                total_sum += item.product.price * item.quantity
            
            order.total_price = total_sum
            order.save()

            cart.items.all().delete()
            return Response ({'detail': 'Order created successfully', 'order_id': order.id}, status=status.HTTP_201_CREATED)
             
                
class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer


class TelegramWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]


    @method_decorator(csrf_exempt)
    def post(self, request, *args, **kwargs):
        update = request.data
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']

            if 'text' in message and message['text'] == '/start':
                self.send_contact_request(chat_id)

            elif 'contact' in message:
                phone_number = message['contact']['phone_number']
                if not phone_number.startswith('+'):
                    phone_number = '+' + phone_number

                    first_name = message['contact'].get('first_name', '')
                    last_name = message['contact'].get('last_name', '')

                    code = ''.join([str(random.randint(0,9)) for _ in range(6)])

                    cache_data = {
                        'phone_number': phone_number,
                        'first_name': first_name,
                        'last_name': last_name,
                        'code': code
                    }

                    cache.set(f'auth_code_{code}', cache_data, timeout=300)

                    self.send_message(chat_id, f'Your verification code is: {code}')

        return HttpResponse({"status": "ok"})
    

    def send_contact_request(self, chat_id):
        url = f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage'

        payload = {
            "chat_id": chat_id,
            "text": "Please share your contact number to proceed with registration:",
            "reply_markup": {
                "keyboard": [
                    [{'text': 'Share Contact', 'request_contact': True}]
                ],
                "one_time_keyboard": True,
                "resize_keyboard": True
            }
        }
        requests.post(url, json=payload)


class LoginWithCodeView(APIView):
    authentication_classes=[]
    permission_classes=[]

    def post(self, request):
        code = request.data.get('code')
        if not code:
            return Response({"error": 'code is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        cache_data = cache.get(f'auth_code_{code}')
        
        if not cache_data:
            return Response({'error': 'Invalid or expired code'}, status=status.HTTP_400_BAD_REQUEST)
        
        phone_number = cache.get("phone_number")
        code = cache.get('code')
        first_name = cache.get('first_name', '')
        last_name = cache.get('last_name', '')

        user, created = User.objects.get_or_create(
            phone_number= phone_number,
            defaults= {
                'username': phone_number,
                'first_name': first_name,
                'last_name': last_name,
            }
        )

        cache.delete(f'auth_code_{code}')

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "phone_number": phone_number,
            "is_new_created": created,
        })