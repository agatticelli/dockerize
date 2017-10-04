#!/usr/bin/env python

import glob
import json
import os
from shutil import copyfile
import sys
from subprocess import Popen, PIPE, check_output

nginxSites = []
proxyStrategy = "standard"

DOCKER_UP = "docker-compose -p {} up -d --build"
SCRIPT_PATH = os.path.abspath(os.path.dirname(sys.argv[0]))

COMPOSE_YML = SCRIPT_PATH + '/docker-compose.yml'

NGINX_PATH = SCRIPT_PATH + "/nginx/"
NGINX_CONF = NGINX_PATH + "conf.d/"

VOLUME_STR = "{}:{}"

DB_PORTS = {
    "redis": "6379",
    "mongo": "27017",
    "mysql": "3306"
}
DB_DATA_PATH = {
    "mysql": "/var/lib/mysql",
    "redis": "/data",
    "mongo": "/data/db"
}
DB_VOLUME = "~/.dockerize/data/{}"

def printMessage(msg):
    msgLen = len(msg) + 10
    print "-" * msgLen
    print "|    " + msg + "    |"
    print "-" * msgLen + "\n"

def clone(src, dst):
    printMessage("Clonning repo: " + src)
    cloneStr = "git clone {} {}"

    if not os.path.isdir( dst ):
        retCode = os.system( cloneStr.format(src, dst) )
        if retCode:
            print "\nCloning Error"
            sys.exit(1)
        else:
            print "\nDONE!\n"
    else:
        print "Repo already exists!"

    print "\n"

def parseDockerson():
    global proxyStrategy
    printMessage("Parsing dockerson.json")
    data = None

    try:
        with open('dockerson.json') as dockerfile:
            data = json.load( dockerfile )
    except Exception, e:
        print "Dockerson File Error:", e
        sys.exit(1)

    repos = data['repos'] if "repos" in data else []
    dbs = data['dbs'] if "dbs" in data else []
    custom = data['custom'] if "custom" in data else []

    if "proxyStrategy" in data:
        proxyStrategy = data['proxyStrategy']

    print "DONE!\n\n"
    return data['project'], repos, dbs, custom


def json2yaml(json, level=0):
    spaces = "  "
    new_line = "\n"
    to_print = ""
    for key, value in json.iteritems():

        to_print += (spaces*level) + key + ":"
        vType = type(value)

        if vType is dict:
            to_print += "\n" + json2yaml(value, level+1)
        elif vType is list:
            for item in value:
                to_print += new_line + (spaces*level+spaces) + "- " + item
            to_print += new_line
        else:
            to_print += " " + value + new_line

    return to_print


def parseDomains(repo):
    if "domains" in repo:
        domain = repo['mainDomain']
    else:
        domain = repo['name'] + '.app'

    if proxyStrategy == "inner":
        domain += ".inner"
    else:
        # Assumes standard
        pass

    return domain


def writeLaravelService(project, repo, version):
    try:
        file = open(COMPOSE_YML, 'a')
        repoName = repo['name']
        repoPath = repo['path']
        aliases = []

        aliases.append(parseDomains(repo))

        dataToWrite = {
            repoName: {
                "build": "./laravel/7.0/" if version == 5 else "./laravel/5.6/",
                "working_dir": "/var/www/" + repoName,
                "volumes": [
                    repoPath + ":/var/www/" + repoName
                ],
                "networks": {
                    project: {
                        "aliases": aliases
                    }
                }
            }
        }

        if "hostname" in repo:
            dataToWrite[repoName]["hostname"] = repo["hostname"]

        file.write(os.linesep + os.linesep + json2yaml(dataToWrite, 1))
    except Exception, e:
        print "Write Laravel Service Error ("+ project +"):", e
        sys.exit(1)
    finally:
        if file:
            file.close()


def writeJavaService(project, repo):
    printMessage("Writing Java Service")
    try:
        file = open(COMPOSE_YML, 'a')
        repoName = repo['name']
        repoPath = repo['path']
        aliases = []

        aliases.append(parseDomains(repo))

        dataToWrite = {
            repoName: {
                "build": {
                    "context": repoPath,
                    "dockerfile": SCRIPT_PATH + "/java/Dockerfile"
                },
                "working_dir": "/usr/src/app/",
                "networks": {
                    project: {
                        "aliases": aliases
                    }
                }
            }
        }
        if "hostname" in repo:
            dataToWrite[repoName]["hostname"] = repo["hostname"]

        file.write(os.linesep * 2 + json2yaml(dataToWrite, 1))
        print "DONE!\n\n"
    except Exception, e:
        print "Write Java Service Error ("+ project +"):", e
        sys.exit(1)
    finally:
        if file:
            file.close()


def writeNodeJSService(project, repo):
    printMessage("Writing NodeJS Service")
    try:
        file = open(COMPOSE_YML, 'a')
        repoName = repo['name']
        repoPath = repo['path']
        aliases = []

        aliases.append(parseDomains(repo))

        dataToWrite = {
            repoName: {
                "build": {
                    "context": repoPath,
                    "dockerfile": SCRIPT_PATH + "/nodejs/Dockerfile"
                },
                "working_dir": "/usr/src/app/",
                "volumes": [
                    VOLUME_STR.format(repoPath, "/usr/src/app"),
                    '/usr/src/app/node_modules'
                ],
                "networks": {
                    project: {
                        "aliases": aliases
                    }
                }
            }
        }
        if "hostname" in repo:
            dataToWrite[repoName]["hostname"] = repo["hostname"]

        file.write( os.linesep * 2 + json2yaml(dataToWrite, 1) )
        print "DONE!\n\n"
    except Exception, e:
        print "Write NodeJS Service Error ("+ project +"):", e
        sys.exit(1)
    finally:
        if file:
            file.close()


def writeRepoCompose(project, repo):
    rType = repo['type']

    if "domains" in repo:
        mainDomain = repo['domains'].split()[0]
        data = {
            "domains": repo['domains'],
            "mainDomain": mainDomain,
            "name": repo['name'],
            "rType": rType
        }
        nginxSites.append(data)
        repo['mainDomain'] = mainDomain

    if "nodejs" in rType:
        writeNodeJSService(project, repo)
    elif "java" in rType:
        writeJavaService(project, repo)
    elif "laravel" in rType:
        if "4.x" in rType:
            writeLaravelService(project, repo, 4)
        else:
            writeLaravelService(project, repo, 5)


def startDCompose():
    with open(COMPOSE_YML, 'w') as file:
        file.write("version: '2'\n")
        file.write("services:\n")


def cleanOldNginxConfs():
    printMessage('Cleaning old nginx .conf files')
    map(os.unlink, glob.glob(NGINX_CONF + '*.conf'))

    print "DONE!\n\n"


def processPlugins(project, repo):
    printMessage('Running plugins for ' + repo['name'])
    if "plugins" in repo:
        plugins = repo['plugins']
        path = repo['path']
        name = repo['name']
        rType = repo['type']
        for plugin in plugins:
            if plugin == "laravel":
                laravelPlugin = './plugins/laravel.sh %s %s %s %s'
                version = rType.split("|")[1]
                os.system(laravelPlugin % (path, project, name, version))
            elif plugin == "composer":
                composerPlugin = './plugins/composer.sh %s'
                os.system(composerPlugin % (path))

    print '\nDONE!\n\n'


def createNginxConfs():
    printMessage('Creating nginx .conf files')
    if len(nginxSites) > 0:
        if not os.path.isdir(NGINX_CONF):
            os.mkdir(NGINX_CONF, 0755)

        for nginxSite in nginxSites:
            domains = nginxSite['domains']
            name = nginxSite['name']
            mainDomain = nginxSite['mainDomain']
            rType = nginxSite['rType']

            if proxyStrategy == "inner":
                mainDomain += '.inner'
            else:
                # Assumes standard
                pass

            src = NGINX_PATH + "vhost.{}.template".format(rType)
            dst = NGINX_CONF + name + ".conf"
            copyfile(src, dst)

            sed_vhost = "sed -i.bak 's/{{ %s }}/%s/g' %s"
            os.system(sed_vhost % ("domains", domains, dst))
            os.system(sed_vhost % ("domain", mainDomain, dst))

            map(os.unlink, glob.glob(NGINX_CONF + '*.bak'))

    print "DONE!\n\n"

def writeNginxCompose(project):
    printMessage('Writing Nginx into docker-compose.yml')
    if len(nginxSites):
        try:
            volumesLink = []
            mainDomains = []
            for nginxSite in nginxSites:
                volumesLink.append(nginxSite['name'])
                mainDomains.append(nginxSite['mainDomain'])

            dataToWrite = {
                "nginx-proxy": {
                    "image": "nginx:1.10",
                    "ports": [
                        "80:80"
                    ],
                    "volumes_from": volumesLink,
                    "links": volumesLink,
                    "volumes": [
                        VOLUME_STR.format("./nginx/conf.d", "/etc/nginx/conf.d")
                    ]
                }
            }

            if proxyStrategy == "inner":
                dataToWrite['nginx-proxy']['networks'] = {
                    project: {
                        "aliases": mainDomains
                    }
                }
            else:
                # Assumes standard
                dataToWrite['nginx-proxy']['networks'] = [project]

            with open(COMPOSE_YML, 'a') as file:
                file.write( os.linesep + json2yaml(dataToWrite, 1) )
            print "DONE!\n\n"
        except Exception, e:
            print "Write Nginx Compose:", e
            sys.exit(1)


def writeNetworkCompose(project):
    printMessage('Writing networks into docker-compose.yml')
    try:
        dataToWrite = {
            "networks": {
                project: {
                    "driver": "bridge"
                }
            }
        }
        with open(COMPOSE_YML, 'a') as file:
            file.write( os.linesep + json2yaml(dataToWrite) )
        print "DONE!\n\n"
    except Exception, e:
        print "Write Network Compose:", e
        sys.exit(1)


def writeEtcHosts(project):
    printMessage('Overriding /etc/hosts')
    if len(nginxSites):
        sites = ""
        for nginxSite in nginxSites:
            sites += nginxSite['domains'] + " "

        sed = "sudo sed -i.bak '/%s/d' /etc/hosts > /dev/null"
        tee = "echo '%s' | sudo tee -a /etc/hosts > /dev/null"

        oldLine = ".*"+project+"-docker.*"
        newLine = "127.0.0.1 " + sites + "#" + project + "-docker"

        os.system( sed % (oldLine) )
        os.system( tee % (newLine) )
    print "DONE!\n\n"


def writeDBCompose(project, dbs):
    printMessage('Writing dbs into docker-compose.yml')
    if len(dbs):
        try:
            for db in dbs:
                volume = DB_VOLUME.format(db)
                dataToWrite = {
                    db: {
                        "build": "./" + db + "/",
                        "networks": {
                            project: {
                                "aliases": [
                                    db + ".db"
                                ]
                            }
                        },
                        "volumes": [
                            VOLUME_STR.format(volume, DB_DATA_PATH[db])
                        ],
                        "ports": [
                            DB_PORTS[db]+":"+DB_PORTS[db]
                        ]
                    }
                }
                with open(COMPOSE_YML, 'a') as file:
                    file.write( os.linesep + json2yaml(dataToWrite, 1) )
        except Exception, e:
            print "Write dbs into docker-compose.yml Error:", e
            sys.exit(1)
    
    print "DONE!\n\n"


def writeCustoms(project, custom):
    printMessage('Writing custom into docker-compose.yml')
    try:
        for service in custom:
            with open(COMPOSE_YML, 'a') as file:
                file.write( os.linesep + json2yaml(service, 1) )

    except Exception, e:
        print "Write Custom Compose Error:", e
        sys.exit(1)

    print "DONE!\n\n"

def startContainers(project):
    printMessage('Starting containers')
    os.system(DOCKER_UP.format(project))
    print "\nDONE!\n\n"

if __name__ == "__main__":
    project, repos, dbs, custom = parseDockerson()

    startDCompose()
    for repo in repos:
        repo['path'] = check_output(['echo {}'.format(repo['into'])],
                                    shell=True).strip()
        
        clone(repo['clone'], repo['path'])
        
        writeRepoCompose(project, repo)

    cleanOldNginxConfs()

    createNginxConfs()

    writeNginxCompose(project)

    writeDBCompose(project, dbs)

    writeCustoms(project, custom)

    writeNetworkCompose(project)

    writeEtcHosts(project)

    startContainers(project)

    for repo in repos:
        processPlugins(project, repo)
