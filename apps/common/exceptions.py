from rest_framework import serializers
from rest_framework.exceptions import APIException


class ConflictError(APIException):
    status_code = 409
    default_detail = "Resource already exists."
    default_code = "conflict"


class BusinessError(APIException):
    status_code = 422
    default_detail = "Business rule violation."
    default_code = "business_error"
