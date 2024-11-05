from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    try:
        refresh_token = request.data["refresh"]
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({"detail": "로그아웃되었습니다."})
    except Exception:
        return Response(
            {"detail": "로그아웃 처리 중 오류가 발생했습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )
