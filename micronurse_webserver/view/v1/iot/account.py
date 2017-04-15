from django.core.cache import cache
from django.utils.translation import ugettext as _
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response
from micronurse_webserver.utils import mqtt_broker_utils
from micronurse_webserver import models
from micronurse_webserver.models import Account
from micronurse_webserver.utils import view_utils
from micronurse_webserver.view import authentication, result_code
from micronurse_webserver.view.check_exception import CheckException
from micronurse_webserver.view.v1.iot import sensor as iot_sensor_view

IOT_TOKEN_VALID_HOURS = 72
CACHE_KEY_IOT_TOKEN_PREFIX = 'iot_token_'


def token_check(req: Request):
    try:
        token = req.META['HTTP_AUTH_TOKEN']
        user_id = authentication.parse_token(token)
    except:
        raise CheckException(status=status.HTTP_401_UNAUTHORIZED, result_code=status.HTTP_401_UNAUTHORIZED,
                             message=_('Invalid token'))
    cache_token = cache.get(CACHE_KEY_IOT_TOKEN_PREFIX + str(user_id))
    if token != cache_token:
        raise CheckException(status=status.HTTP_401_UNAUTHORIZED, result_code=status.HTTP_401_UNAUTHORIZED,
                             message=_('Invalid token'))
    cache.set(CACHE_KEY_IOT_TOKEN_PREFIX + str(user_id), cache_token, IOT_TOKEN_VALID_HOURS * 3600)
    return Account(user_id=user_id)


@api_view(['PUT'])
def login(request: Request):
    try:
        account = Account.objects.filter(phone_number=request.data['phone_number']).get()
        if not account.password == request.data['password']:
            raise CheckException(result_code=result_code.IOT_LOGIN_INCORRECT_PASSWORD, message=_('Incorrect password'),
                                 status=status.HTTP_401_UNAUTHORIZED)
        if not account.account_type == models.ACCOUNT_TYPE_OLDER:
            raise CheckException(result_code=result_code.IOT_LOGIN_ACCOUNT_TYPE_ERROR,
                                 message=_('Only older can login'), status=422)
        token_str = authentication.get_token(account.user_id)
        cache.set(CACHE_KEY_IOT_TOKEN_PREFIX + str(account.user_id), token_str, IOT_TOKEN_VALID_HOURS * 3600)
        res = view_utils.get_json_response(result_code=result_code.SUCCESS, message=_('Login successfully'),
                                           status=status.HTTP_201_CREATED, token=token_str)
        return res
    except Account.DoesNotExist:
        raise CheckException(result_code=result_code.IOT_LOGIN_USER_NOT_EXIST, message=_('User does not exist'),
                             status=status.HTTP_401_UNAUTHORIZED)


@api_view(['DELETE'])
def logout(req: Request):
    user = token_check(req)
    cache.delete(CACHE_KEY_IOT_TOKEN_PREFIX + str(user.user_id))
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
def check_login(req: Request, user_id: str):
    user = token_check(req)
    if str(user.user_id) != user_id:
        raise CheckException(status=status.HTTP_401_UNAUTHORIZED, result_code=status.HTTP_401_UNAUTHORIZED,
                             message=_('Token does not match this user.'))
    mqtt_broker_utils.subscribe_topic(topic=iot_sensor_view.TOPIC_SENSOR_DATA_REPORT, topic_user=user, qos=1)
    return view_utils.get_json_response()


@api_view(['GET'])
def get_account_info(req: Request):
    user = token_check(req)
    user = Account.objects.filter(user_id=user.user_id).get()
    return view_utils.get_json_response(user=view_utils.get_user_info_dict(user=user))
