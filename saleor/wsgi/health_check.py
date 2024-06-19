import json


def health_check(application, health_url):
    def health_check_wrapper(environ, start_response):
        if environ.get("PATH_INFO") == health_url:
            with open("package.json", encoding="utf-8") as f:
                data = json.load(f)
            start_response("200 OK", [("Content-Type", "application/json")])
            response = {"name": data.get("name"), "version": data.get("version")}
            return [json.dumps(response).encode()]
        return application(environ, start_response)

    return health_check_wrapper
