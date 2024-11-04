from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from datetime import datetime, timezone

@api_view(["POST"])
def login(request):
    try:
        # 기존 토큰 생성 로직...
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        
        response = Response({
            "access": access_token,
            "user": UserSerializer(user).data
        })
        
        # 리프레시 토큰을 HttpOnly 쿠키로 설정
        response.set_cookie(
            'refresh_token',
            str(refresh),
            httponly=True,
            secure=not settings.DEBUG,  # 개발환경에서는 False, 운영환경에서는 True
            samesite='Lax',
            max_age=24 * 60 * 60  # 24시간
        )
        
        return response
        
    except Exception as e:
        return Response(
            {"detail": "로그인에 실패했습니다."},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    try:
        response = Response({"detail": "로그아웃되었습니다."})
        response.delete_cookie('refresh_token')
        return response
    except Exception:
        return Response(
            {"detail": "로그아웃 처리 중 오류가 발생했습니다."},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(["POST"])
def token_refresh(request):
    try:
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response(
                {"detail": "Refresh token not found"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        refresh = RefreshToken(refresh_token)
        access_token = str(refresh.access_token)
        
        return Response({
            "access": access_token
        })
        
    except Exception as e:
        return Response(
            {"detail": "토큰 갱신에 실패했습니다."},
            status=status.HTTP_401_UNAUTHORIZED
        )
