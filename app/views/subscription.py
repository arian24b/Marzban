import re
from datetime import datetime

from fastapi import Depends, Header, HTTPException, Path, Request, Response
from fastapi.responses import HTMLResponse
from datetime import datetime
from app import app, settings
from app.db import Session, crud, get_db
from app.models.user import UserResponse
from app.templates import render_template
from app.utils.jwt import get_subscription_payload
from app.utils.share import encode_title, generate_subscription
from config import (
    SUBSCRIPTION_PAGE_TEMPLATE,
    XRAY_SUBSCRIPTION_PATH
)


@app.get("/%s/{token}/" % XRAY_SUBSCRIPTION_PATH, tags=['Subscription'])
@app.get("/%s/{token}" % XRAY_SUBSCRIPTION_PATH, include_in_schema=False)
def user_subscription(token: str,
                      request: Request,
                      db: Session = Depends(get_db),
                      user_agent: str = Header(default="")):
    """
    Subscription link, V2ray and Clash supported
    """
    accept_header = request.headers.get("Accept", "")

    def get_subscription_user_info(user: UserResponse) -> dict:
        return {
            "upload": 0,
            "download": user.used_traffic,
            "total": user.data_limit,
            "expire": user.expire,
        }

    sub = get_subscription_payload(token)
    if not sub:
        return Response(status_code=204)

    dbuser = crud.get_user(db, sub['username'])
    if not dbuser or dbuser.created_at > sub['created_at']:
        return Response(status_code=204)

    if dbuser.sub_revoked_at and dbuser.sub_revoked_at > sub['created_at']:
        return Response(status_code=204)

    user: UserResponse = UserResponse.from_orm(dbuser)

    if "text/html" in accept_header:
        return HTMLResponse(
            render_template(
                SUBSCRIPTION_PAGE_TEMPLATE,
                {"user": user}
            )
        )

    response_headers = {
        "content-disposition": f'attachment; filename="{user.username}"',
        "profile-web-page-url": str(request.url),
        "support-url": settings.get('subscription_support_url_header', ''),
        "profile-title": encode_title(settings.get('subscription_page_title', 'Subscription')),
        "profile-update-interval": settings.get('subscription_update_interval_header', 12),
        "subscription-userinfo": "; ".join(
            f"{key}={val}"
            for key, val in get_subscription_user_info(user).items()
            if val is not None
        )
    }

    crud.update_user_sub(db, dbuser, user_agent)

    if re.match('^([Cc]lash-verge|[Cc]lash-?[Mm]eta)', user_agent):
        conf = generate_subscription(user=user, config_format="clash-meta", as_base64=False)
        return Response(content=conf, media_type="text/yaml", headers=response_headers)

    elif re.match('^([Cc]lash|[Ss]tash)', user_agent):
        conf = generate_subscription(user=user, config_format="clash", as_base64=False)
        return Response(content=conf, media_type="text/yaml", headers=response_headers)

    elif re.match('^(SFA|SFI|SFM|SFT)', user_agent):
        conf = generate_subscription(user=user, config_format="sing-box", as_base64=False)
        return Response(content=conf, media_type="application/json", headers=response_headers)

    elif re.match('^(SS|SSR|SSD|SSS|Outline|Shadowsocks|SSconf)', user_agent):
        conf = generate_subscription(user=user, config_format="outline", as_base64=False)
        return Response(content=conf, media_type="application/json", headers=response_headers)

    else:
        conf = generate_subscription(user=user, config_format="v2ray", as_base64=True)
        return Response(content=conf, media_type="text/plain", headers=response_headers)


@app.get("/%s/{token}/info" % XRAY_SUBSCRIPTION_PATH, tags=['Subscription'], response_model=UserResponse)
def user_subscription_info(token: str,
                           db: Session = Depends(get_db)):
    sub = get_subscription_payload(token)
    if not sub:
        return Response(status_code=404)

    dbuser = crud.get_user(db, sub['username'])
    if not dbuser or dbuser.created_at > sub['created_at']:
        return Response(status_code=404)

    elif dbuser.sub_revoked_at and dbuser.sub_revoked_at > sub['created_at']:
        return Response(status_code=404)

    return dbuser


@app.get("/%s/{token}/usage" % XRAY_SUBSCRIPTION_PATH, tags=['Subscription'])
def user_get_usage(token: str,
                   start: str = None,
                   end: str = None,
                   db: Session = Depends(get_db)):

    sub = get_subscription_payload(token)
    if not sub:
        return Response(status_code=204)

    dbuser = crud.get_user(db, sub['username'])
    if not dbuser or dbuser.created_at > sub['created_at']:
        return Response(status_code=204)

    if dbuser.sub_revoked_at and dbuser.sub_revoked_at > sub['created_at']:
        return Response(status_code=204)

    if start is None:
        start_date = datetime.fromtimestamp(datetime.utcnow().timestamp() - 30 * 24 * 3600)
    else:
        start_date = datetime.fromisoformat(start)

    if end is None:
        end_date = datetime.utcnow()
    else:
        end_date = datetime.fromisoformat(end)

    usages = crud.get_user_usages(db, dbuser, start_date, end_date)

    return {"usages": usages, "username": dbuser.username}


@app.get("/%s/{token}/{client_type}" % XRAY_SUBSCRIPTION_PATH, tags=['Subscription'])
def user_subscription_with_client_type(
    token: str,
    request: Request,
    client_type: str = Path(..., regex="sing-box|clash-meta|clash|outline|v2ray"),
    db: Session = Depends(get_db),
):
    """
    Subscription link, v2ray, clash, sing-box, outline and clash-meta supported
    """

    def get_subscription_user_info(user: UserResponse) -> dict:
        return {
            "upload": 0,
            "download": user.used_traffic,
            "total": user.data_limit,
            "expire": user.expire,
        }

    sub = get_subscription_payload(token)
    if not sub:
        return Response(status_code=204)

    dbuser = crud.get_user(db, sub['username'])
    if not dbuser or dbuser.created_at > sub['created_at']:
        return Response(status_code=204)

    if dbuser.sub_revoked_at and dbuser.sub_revoked_at > sub['created_at']:
        return Response(status_code=204)

    user: UserResponse = UserResponse.from_orm(dbuser)

    response_headers = {
        "content-disposition": f'attachment; filename="{user.username}"',
        "profile-web-page-url": str(request.url),
        "support-url": settings.get('subscription_support_url_header', ''),
        "profile-title": encode_title(settings.get('subscription_page_title', 'Subscription')),
        "profile-update-interval": settings.get('subscription_update_interval_header', 12),
        "subscription-userinfo": "; ".join(
            f"{key}={val}"
            for key, val in get_subscription_user_info(user).items()
            if val is not None
        )
    }

    if client_type == "clash-meta":
        conf = generate_subscription(user=user, config_format="clash-meta", as_base64=False)
        return Response(content=conf, media_type="text/yaml", headers=response_headers)

    elif client_type == "sing-box":
        conf = generate_subscription(user=user, config_format="sing-box", as_base64=False)
        return Response(content=conf, media_type="application/json", headers=response_headers)

    elif client_type == "clash":
        conf = generate_subscription(user=user, config_format="clash", as_base64=False)
        return Response(content=conf, media_type="text/yaml", headers=response_headers)

    elif client_type == "v2ray":
        conf = generate_subscription(user=user, config_format="v2ray", as_base64=True)
        return Response(content=conf, media_type="text/plain", headers=response_headers)

    elif client_type == "outline":
        conf = generate_subscription(user=user, config_format="outline", as_base64=False)
        return Response(content=conf, media_type="application/json", headers=response_headers)

    else:
        raise HTTPException(status_code=400, detail="Invalid subscription type")
