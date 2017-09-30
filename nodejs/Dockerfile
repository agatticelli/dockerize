FROM node:latest

RUN npm install -g nodemon

ADD package.json /tmp/package.json
RUN cd /tmp && npm install
RUN mkdir -p /usr/src/app && cp -a /tmp/node_modules /usr/src/app

WORKDIR /usr/src/app
ADD . /usr/src/app

ENV PORT 3000
EXPOSE 3000

CMD ["npm", "start"]