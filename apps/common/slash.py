from django.urls import resolve, Resolver404


class AppendSlashMiddleware:
    """Resolve URLs by appending a trailing slash if needed, without redirecting.

    Django's APPEND_SLASH sends a 301/308 redirect which breaks POST requests.
    This middleware instead rewrites the request path internally so the URL
    matcher can find the view.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            resolve(request.path)
        except Resolver404:
            if not request.path.endswith("/"):
                test_path = request.path + "/"
                try:
                    resolve(test_path)
                except Resolver404:
                    pass
                else:
                    request.path = test_path
                    request.path_info = test_path

        return self.get_response(request)
