from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import ShiftAssignment

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id", "email", "first_name", "last_name", "full_name",
            "role", "shift", "phone", "machine_assignment", "assigned_machines",
            "is_on_duty", "is_staff", "is_active", "date_joined",
        )
        read_only_fields = ("id", "date_joined", "is_staff")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = (
            "id", "email", "first_name", "last_name", "role",
            "shift", "phone", "machine_assignment", "assigned_machines", "password", "password2",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password2"):
            raise serializers.ValidationError({"password2": "Les mots de passe ne correspondent pas."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")
        assigned_machines = validated_data.pop("assigned_machines", None)
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        if assigned_machines is not None:
            user.assigned_machines.set(assigned_machines)
        return user


class MeSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        read_only_fields = UserSerializer.Meta.read_only_fields + (
            "email", "role", "machine_assignment", "assigned_machines", "is_staff", "is_active",
        )


class ShiftAssignmentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    user_role = serializers.CharField(source="user.role", read_only=True, default="")
    machine_code = serializers.CharField(source="machine.code", read_only=True, default="")

    class Meta:
        model = ShiftAssignment
        fields = (
            "id", "user", "user_name", "user_role", "machine", "machine_code",
            "shift", "starts_at", "ends_at", "created_at",
        )
        read_only_fields = ("id", "created_at")


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        token["full_name"] = user.full_name
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
