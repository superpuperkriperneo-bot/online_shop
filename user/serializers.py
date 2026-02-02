from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify
from .models import Categories, Products, CustomUser, Cart, CartItem, Order, OrderItem, Reviews

UserModel = get_user_model()


class ProductsSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Products
        fields = ('name', 'category', 'category_name', 'price', 'description', 'discount_price', 'special_offer', 'image', 'stock', 'is_active')
        read_only = ('created_at', 'updated_at', 'slug')


class CategoriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categories
        fields = ('name',)
        read_only = ('slug', 'parent')



class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    def create(self, validated_data):

        user = UserModel.objects.create_user(
            username= validated_data['username'],
            password= validated_data['password']
        )

        return user

    class Meta:
        model = CustomUser
        fields = ('username', 'phone_number', 'password', 'address')


class UpdatePasswordSerializer(serializers.ModelSerializer):
    old_password = serializers.CharField(required=True)
    brand_new_password = serializers.CharField(required=True, validators=[validate_password])
    confirm_password = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['brand_new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password' : " the passwords didn't match" })
        return attrs


class CartItemSerializer(serializers.ModelSerializer):
    product_details = ProductsSerializer(source='product', read_only=True)
    product = serializers.PrimaryKeyRelatedField(queryset=Products.objects.all(), write_only=True)
    class Meta:
        model = CartItem
        fields = ('id', 'product_details', 'product', 'quantity')


class CartSerializer(serializers.ModelSerializer):
    total_price = serializers.SerializerMethodField()
    items = CartItemSerializer(many=True, read_only=True)

    def in_total(self, obj):
        items = obj.items.all()
        prices = []

        for item in items:
            prices.append(item.in_total())

        return sum(prices)
    
    class Meta:
        model = Cart
        fields = ('user', 'items')


class CheckoutSerializer(serializers.ModelSerializer):
    address = serializers.CharField(max_length=150, required=True)
    cart_items = serializers.ListField(
        child=serializers.IntegerField(), write_only=True
    )

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ('user', 'total_price', 'status')
        read_only = ('created_at')


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductsSerializer(read_only=True)
    class Meta:
        model = OrderItem
        fields = ('order', 'product', 'quantity', 'price')


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reviews
        fields = ('user', 'product', 'rating', 'comment')