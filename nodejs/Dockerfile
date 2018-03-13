FROM node:latest

ARG registry=https://registry.npmjs.org

RUN npm install -g nodemon forever

ADD package.json /tmp/
RUN cd /tmp && npm install --registry ${registry}
RUN mkdir -p /usr/src/app && cp -a /tmp/node_modules /usr/src/app

WORKDIR /usr/src/app
ADD . /usr/src/app

CMD ["npm", "start"]
