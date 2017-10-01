FROM openjdk:8

# Install maven
RUN apt-get update
RUN apt-get install -y maven

WORKDIR /usr/src/app

# Prepare by downloading dependencies
ADD pom.xml /usr/src/app/pom.xml

# Adding source, compile and package into a fat jar
ADD src /usr/src/app/src
RUN ["mvn", "package"]

EXPOSE 8080
CMD ["java", "-jar", "target/api-1.0.0.jar"]