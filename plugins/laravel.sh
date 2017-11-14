#!/usr/bin/env bash

source ./plugins/colors.sh

path=$1
project=$2
repo=$3
version="$4"
current=$(pwd)

cd $path

version_regex="^5(\.[0-9])?$"

if [[ "$version" =~ $version_regex ]]; then
	if [ ! -f ".env" ]; then
	    echo -e "${LIGHTRED}-------> Copying .env file ...${NONE} ${YELLOW}EDIT LATER!${NONE}"
	    cp ".env.example" ".env"
	fi
else # is 4.2
	if [ ! -d "app/config/local" ]; then
		mkdir -p app/config/local

	    echo -e "${LIGHTRED}-------> Creating app/config/local/app.php ...${NONE} ${YELLOW}EDIT LATER!${NONE}!"
		cp app/config/app.base.php app/config/local/app.php
		cp app/config/app.base.php app/config/app.php
	    
	    echo -e "${LIGHTRED}-------> Creating app/config/local/database.php ...${NONE} ${YELLOW}EDIT LATER!${NONE}!"
		cp app/config/database.base.php app/config/local/database.php
		cp app/config/database.base.php app/config/database.php
	    
	    echo -e "${LIGHTRED}-------> Creating .env.local.php ...${NONE} ${YELLOW}EDIT LATER!${NONE}!"
	    cp .env.example .env.local.php
	fi
fi

cd $current

$(dirname $0)/composer.sh $path

if [[ "$version" =~ $version_regex ]]; then
	sudo chmod -R 777 $path/storage
	sudo chmod -R 777 $path/bootstrap/cache
else
	sudo chmod -R 777 $path/app/storage
fi

echo -e "${LIGHTRED}-------> Running artisan key:generate${NONE}"
docker-compose -p $project exec $repo php artisan key:generate

echo -e "${LIGHTRED}-------> Running artisan optimize${NONE}"
docker-compose -p $project exec $repo php artisan optimize
