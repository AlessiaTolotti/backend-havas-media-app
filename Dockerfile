ARG PYTHON_VERSION=3.13

FROM python:${PYTHON_VERSION} AS build

WORKDIR /usr/app
RUN python -m venv /usr/app/venv
ENV PATH="/usr/app/venv/bin:$PATH"

COPY backend_py/requirements.txt .

RUN pip install -r requirements.txt


FROM python:${PYTHON_VERSION}-slim AS final

WORKDIR /usr/app


COPY --from=build /usr/app/venv ./venv
COPY backend_py/ .

ENV PATH="/usr/app/venv/bin:$PATH"

# CMD [ "python", "app.py" ]
#CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]
CMD ["gunicorn", "-w", "2","-b", "0.0.0.0:8000", "app:app", "--timeout", "300"]
