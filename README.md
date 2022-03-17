# Apilytics for Python

[![pypi](https://img.shields.io/pypi/v/apilytics)](https://pypi.org/project/apilytics/)
[![ci](https://github.com/apilytics/apilytics-python/actions/workflows/ci.yml/badge.svg)](https://github.com/apilytics/apilytics-python/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/apilytics/apilytics-python/branch/master/graph/badge.svg?token=GIW1NZ7UAJ)](https://codecov.io/gh/apilytics/apilytics-python)
[![mypy checked](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org)
[![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![python versions](https://img.shields.io/pypi/pyversions/apilytics)](#what-python-versions-does-the-package-work-with)
[![license](https://img.shields.io/pypi/l/apilytics.svg)](https://github.com/apilytics/apilytics-python/blob/master/LICENSE)

Apilytics is a service that lets you analyze operational, performance and security metrics from your APIs easily.

<img src="https://www.apilytics.io/mock-ups/time-frame.gif" alt="Apilytics dashboard animation" width="600" height="300" />

## Installation

1. Sign up and get your API key from https://apilytics.io - we offer a completely free trial with no credit card required!

2. Install this package:

```sh
pip install apilytics
```

3. Enable the middleware and set your API key:\
   _A good practice is to securely store the API key as an environment variable.
   You can leave the env variable unset in e.g. development and test environments,
   the middleware will be automatically disabled if the key is `None`._

### Django

`settings.py`:

```python
import os

APILYTICS_API_KEY = os.getenv("APILYTICS_API_KEY")

MIDDLEWARE = [
    "apilytics.django.ApilyticsMiddleware",  # Ideally the first middleware in the list.
    # ...
]
```

### FastAPI

`main.py`:

```python
import os

from apilytics.fastapi import ApilyticsMiddleware
from fastapi import FastAPI

app = FastAPI()

# Ideally the first middleware you add.
app.add_middleware(ApilyticsMiddleware, api_key=os.getenv("APILYTICS_API_KEY"))
```

### Other Python Frameworks

You can easily build your own middleware which measures the execution time and sends the metrics:

`my_apilytics_middleware.py`:

```python
import os

from apilytics.core import ApilyticsSender


def my_apilytics_middleware(request, get_response):
    api_key = os.getenv("APILYTICS_API_KEY")
    if not api_key:
        return get_response(request)

    with ApilyticsSender(
        api_key=api_key,
        path=request.path,
        query=request.query_string,
        method=request.method,
        request_size=len(request.body),
        user_agent=request.headers.get("user-agent"),
        ip=request.headers.get("x-forwarded-for", "").split(",")[0].strip(),
    ) as sender:
        response = get_response(request)
        sender.set_response_info(
            status_code=response.status_code,
            response_size=len(response.body),
        )
    return response
```

## Frequently Asked Questions

### Does the middleware slow down my backend?

- No. The middleware does all of its requests to the Apilytics API in a background thread pool,
  so it will not slow down your normal request handling.

### What 3rd party dependencies does `apilytics` have?

- None besides the frameworks that you use it in.

### What Python versions does the package work with?

- `apilytics` is tested to work on all the currently [supported versions of Python](https://devguide.python.org/#status-of-python-branches): 3.7, 3.8, 3.9, and 3.10.
