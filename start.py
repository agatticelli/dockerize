#!/usr/bin/env python

from argparse import ArgumentParser
import glob
import json
import os
import re
from shutil import copyfile
import sys
from subprocess import Popen, PIPE, check_output
from time import sleep
import webbrowser

nginxSites = []
proxyStrategy = "standard"

DOCKER_UP = "docker-compose -p {} up -d{}"
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
DB_VOLUME = "~/.dockerize/data/{}/{}"

PHPV_REGEX = r"^php\|(5|7)[.\d+]*$"


parser = ArgumentParser()
parser.add_argument('-o', '--open', dest='open', help='Url to open at start')
parser.add_argument('-b', '--build', action='store_true',
                    dest='build', help='Rebuild containers')
parser.add_argument('-d', '--dockerson', dest='dockerson',
                    help='Dockerson file to load')

args = parser.parse_args()

def printMessage(msg):
    msgLen = len(msg) + 10
    print "\033[1;31m-" * msgLen
    print "|    " + msg + "    |"
    print "-" * msgLen + "\n\033[0m"

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
        if args.dockerson:
            dockersonFile = args.dockerson + '.dockerson.json'
            if not os.path.isfile(dockersonFile):
                raise Exception('El archivo %s no existe' % dockersonFile)
        else:
            dockersonFile = 'dockerson.json'

        with open(dockersonFile) as dockerfile:
            data = json.load(dockerfile)

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


def parsePorts(repo):
    return repo['ports'] if 'ports' in repo else []


def writeService(project, repo, rType, extra):
    printMessage("Writing %s Service" % rType)
    try:
        file = open(COMPOSE_YML, 'a')
        repoName = repo['name']
        repoPath = repo['path']

        aliases = [parseDomains(repo)]
        ports = parsePorts(repo)

        repoDockerfile = '/'.join([repoPath, 'Dockerfile'])
        if os.path.isfile(repoDockerfile):
            dockerfile = repoDockerfile
        else:
            dockerfile = '/'.join([SCRIPT_PATH, rType, 'Dockerfile'])

        dataToWrite = {
            repoName: {
                "build": {
                    "context": repoPath,
                    "dockerfile": dockerfile
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

        if "dns" in repo:
            dataToWrite[repoName]['dns'] = repo['dns']

        if len(ports):
            dataToWrite[repoName]["ports"] = ports

        if extra:
            for key in extra:
                dataToWrite[repoName][key] = extra[key]

        file.write(os.linesep * 2 + json2yaml(dataToWrite, 1))
        print "DONE!\n\n"
    except Exception, e:
        print "Write %s Service Error (%s): %s" % (rType, project, e)
        raise e
    finally:
        if file:
            file.close()

def writePythonService(project, repo):
    try:
        extra = {
            "volumes": [
                VOLUME_STR.format(repo['path'], "/usr/src/app"),
            ]
        }
        writeService(project, repo, 'Python', extra)
    except Exception, e:
      sys.exit(1)

def writePHPService(project, repo, version):
    try:
        pathInDocker = "/usr/src/app/" + repo['name']
        extra = {
            "volumes": [
                VOLUME_STR.format(repo['path'], pathInDocker)
            ],
            "working_dir": pathInDocker,
            "build": "./php/7.0/" if version == 7 else "./php/5.6/"
        }
        writeService(project, repo, 'PHP:'+str(version), extra)
    except Exception, e:
        sys.exit(1)


def writeJavaService(project, repo):
    try:
        writeService(project, repo, 'Java', None)
    except Exception, e:
        sys.exit(1)


def writeNodeJSService(project, repo):
    try:
        extra = {
            "volumes": [
                VOLUME_STR.format(repo['path'], "/usr/src/app"),
                '/usr/src/app/node_modules'
            ]
        }
        writeService(project, repo, 'NodeJS', extra)
    except Exception, e:
        sys.exit(1)


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
    elif "php" in rType:
        matches = re.search(PHPV_REGEX, rType)
        if matches:
            version = int(matches.groups()[0])
            writePHPService(project, repo, version)
        else:
            print "ERROR: php bad version", rType
            sys.exit(1)
    elif "python" in rType:
        writePythonService(project, repo)


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
            if "laravel" in plugin:
                laravelPlugin = './plugins/laravel.sh %s %s %s %s'
                version = plugin.split("|")[1]
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

            src = NGINX_PATH + "vhost.{}.template".format(rType.split("|")[0])
            dst = NGINX_CONF + name + ".conf"
            copyfile(src, dst)

            sed_vhost = "sed -i.bak 's/{{ %s }}/%s/g' %s"
            os.system(sed_vhost % ("domains", domains, dst))
            os.system(sed_vhost % ("domain", mainDomain, dst))
            os.system(sed_vhost % ("repo", name, dst))

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

        newLine = "127.0.0.1 " + sites + "#" + project + "-docker"
        grep = 'grep "' + newLine + '" /etc/hosts > /dev/null'

        if os.system(grep):
            sed = "sudo sed -i.bak '/%s/d' /etc/hosts > /dev/null"
            tee = "echo '%s' | sudo tee -a /etc/hosts > /dev/null"
            oldLine = ".*"+project+"-docker.*"
            os.system( sed % (oldLine) )
            os.system( tee % (newLine) )

    print "DONE!\n\n"


def writeDBCompose(project, dbs):
    printMessage('Writing dbs into docker-compose.yml')
    if len(dbs):
        try:
            for db in dbs:
                volume = DB_VOLUME.format(db, project)
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
    opts = ""
    if args.build:
        opts += " --build"
    os.system(DOCKER_UP.format(project, opts))
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

    if args.open:
        open_ = args.open
        opened = False
        try:
            for repo in repos:
                if repo['name'] == open_:
                    if "mainDomain" in repo:
                        print("Opening web browser...")
                        sleep(5)
                        webbrowser.open("http://" + repo['mainDomain'])
                        opened = True
                        break
                    else:
                        msg = "OPEN: No domains for repo {}"
                        raise Exception(msg.format(open_))
            if not opened:
                msg = "OPEN: {} not found in repos list"
                raise Exception(msg.format(open_))
        except Exception as e:
            print(e)
