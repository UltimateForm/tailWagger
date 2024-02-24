FROM python:3.10.2

WORKDIR /bot

COPY ./Pipfile .

COPY ./.env .

RUN pip install pipenv

RUN pipenv install

COPY ./main.py ./

COPY ./parse_utilities.py .

CMD ["pipenv", "run", "python", "main.py"]deploy