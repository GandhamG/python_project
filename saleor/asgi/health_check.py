import json


def health_check(application, health_url):
    async def health_check_wrapper(scope, receive, send):
        if scope.get("path") != health_url:
            await application(scope, receive, send)
            return
        if scope.get("path") == health_url:
            with open("package.json", encoding="utf-8") as f:
                data = json.load(f)
            response = {"name": data.get("name"), "version": data.get("version")}
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": json.dumps(response).encode(),
                }
            )

    return health_check_wrapper
