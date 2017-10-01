FROM mysql:latest

ENV MYSQL_ROOT_PASSWORD=root

ADD entrypoint/*.sql /docker-entrypoint-initdb.d/

EXPOSE 3306

CMD ["mysqld"]