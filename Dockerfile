FROM python:3.7

LABEL "author"="zengnan@gmail.com"

ENV APPDIR /app

COPY requirements.txt setup.py $APPDIR/

RUN pip install -r $APPDIR/requirements.txt

RUN python $APPDIR/setup.py install

CMD ["stunnel_server", "-p", "7777"]