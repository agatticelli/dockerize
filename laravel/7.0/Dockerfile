FROM php:7.0-fpm

RUN apt-get update

RUN apt-get install -y python php5-cli php5-mysql \
    php5-redis php5-readline libmcrypt-dev libcurl4-gnutls-dev zlib1g-dev \
    libicu-dev g++ libxml2-dev libpq-dev git zip unzip

RUN git clone https://github.com/phpredis/phpredis.git /usr/src/php/ext/redis \
 && docker-php-ext-install pdo pdo_mysql curl json xml redis

 RUN pecl install mongodb && \
     echo "extension=mongodb.so" > /usr/local/etc/php/conf.d/ext-mongodb.ini

RUN apt-get autoremove && apt-get autoclean \
 && rm -rf /var/lib/apt/lists/*
