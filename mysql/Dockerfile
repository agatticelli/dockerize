FROM mysql:latest

ENV MYSQL_ROOT_PASSWORD=root

ADD ./docker-entrypoint-initdb.d/*.sql /docker-entrypoint-initdb.d/

EXPOSE 3306

CMD ["mysqld"]
