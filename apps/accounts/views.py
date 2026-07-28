from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.audit.services import log_activity
from apps.common.permissions import IsAdmin, IsAdminOrManagerOrMaintenance

from .models import CustomUser
from .serializers import LoginSerializer, MeSerializer, RegisterSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user
        log_activity(user, "auth.login", "CustomUser", user.pk, user.email)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        try:
            RefreshToken(request.data.get("refresh"))
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        log_activity(request.user, "auth.logout", "CustomUser", request.user.pk, request.user.email)
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(MeSerializer(request.user).data)

    def patch(self, request):
        u = request.user
        for f in ("first_name", "last_name", "phone", "shift", "is_on_duty"):
            if f in request.data:
                setattr(u, f, request.data[f])
        u.save()
        return Response(MeSerializer(u).data)


class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all().order_by("last_name", "first_name")
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated, IsAdmin)
    filterset_fields = ("role", "shift", "is_on_duty")
    search_fields = ("email", "first_name", "last_name", "phone")

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), IsAdminOrManagerOrMaintenance()]
        return [permission() for permission in self.permission_classes]

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, IsAdmin])
    def register(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
