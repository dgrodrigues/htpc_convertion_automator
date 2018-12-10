import sys
import os
import shutil
import time
import subprocess

from autoprocess import autoProcessMovie, sonarr
from readSettings import ReadSettings
from mkvtomp4 import MkvtoMp4

import logging
from logging.config import fileConfig
from os import listdir
from os.path import isfile, join

f = open("/home/pi/log/transmission.log", "a")
f.write("TR_APP_VERSION: " + sys.argv[1] + "\n")
f.write("TR_TIME_LOCALTIME: " + sys.argv[2] + "\n")
f.write("TR_TORRENT_DIR: " + sys.argv[3] + "\n")
f.write("TR_TORRENT_HASH: " + sys.argv[4] + "\n")
f.write("TR_TORRENT_ID: " + sys.argv[5] + "\n")
f.write("TR_TORRENT_NAME: " + sys.argv[6] + "\n")
f.write("\n")


fileConfig(os.path.join(os.path.dirname(sys.argv[0]), 'logging.ini'), defaults={'logfilename': os.path.join(os.path.dirname(sys.argv[0]), 'info.log').replace("\\", "/")})
log = logging.getLogger("transmissionPostProcess")

try:
	log.info("Transmission post processing started.")

	settings = ReadSettings(os.path.dirname(sys.argv[0]), "autoProcess.ini")
	remove = settings.transmission['remove']

	if len(sys.argv) < 6:
		log.error("Not enough command line parameters present, are you launching this from Transmission?")
		sys.exit()

except Exception as err:
	log.error("Error: %s." % err.message)
	sys.exit()


try:
	path = str(sys.argv[3])
	torrent_name = str(sys.argv[6])
	torrent_id = str(sys.argv[4])
	delete_dir = None
	original_delete_dir = os.path.join(path + "/" + torrent_name)

	log.debug("Path: %s." % path)
	log.debug("Torrent: %s." % torrent_name)
	log.debug("Hash: %s." % torrent_id)

	isSonarr = True if 'Sonarr' in path else False
	isCouchPotato = True if 'CouchPotato' in path else False

	log.debug("IS FROM SONARR: %s." % str(isSonarr))
	log.debug("IS FROM COUCHPOTTO: %s." % str(isCouchPotato))

	if not isSonarr and not isCouchPotato:
		log.error("No valid origin detected.")
		sys.exit()

except Exception as err:
	log.error("Error Category: %s." % err.message)
	sys.exit()

if os.path.isfile(os.path.join(path + "/" + torrent_name)):
	files = [os.path.join(path + "/" + torrent_name)]
else:
	files = [f for f in os.listdir(path + "/" + torrent_name) if os.path.isfile(os.path.join(path + "/" + torrent_name, f))]

log.debug("List of files in torrent: " + str(files))

if settings.transmission['convert']:
	log.debug("Should convert files")

	# Check for custom Deluge output_dir
	if settings.transmission['output_dir']:
		settings.output_dir = settings.transmission['output_dir']
		log.debug("Overriding output_dir to %s." % settings.transmission['output_dir'])

	# Perform conversion.
	settings.delete = False
	if not settings.output_dir:
		suffix = "-convert"

	torrent_name = torrent_name[:260-len(suffix)]
	settings.output_dir = os.path.join(path, ("%s%s" % (torrent_name, suffix)))
	log.debug("Output Path: %s." % settings.output_dir)

	if not os.path.exists(settings.output_dir):
		os.mkdir(settings.output_dir)
		delete_dir = settings.output_dir
		log.debug("Delete Path: %s." % delete_dir)

	converter = MkvtoMp4(settings)

	for filename in files:
		inputfile = os.path.join(path + "/" + torrent_name, filename)
		if MkvtoMp4(settings).validSource(inputfile):
			log.info("Converting file %s at location %s." % (inputfile, settings.output_dir))
			try:
				output = converter.process(inputfile)
			except:
				log.exception("Error converting file %s." % inputfile)

	path = converter.output_dir
	log.debug("Converter Path: %s." % path)

else:
	log.debug("Should not convert")
	suffix = "-copy"
	torrent_name = torrent_name[:260-len(suffix)]
	newpath = os.path.join(path + "/" + torrent_name, ("%s%s" % (torrent_name, suffix)))
	if not os.path.exists(newpath):
		os.mkdir(newpath)
		for filename in files:
			inputfile = os.path.join(path + "/" + torrent_name, filename)
			log.info("Copying file %s to %s." % (inputfile, newpath))
			shutil.copy(inputfile, newpath)

	path = newpath
	delete_dir = newpath


# Send to CouchPotato
if (isCouchPotato):
	log.info("Passing %s directory to Couch Potato." % path)
	autoProcessMovie.process(path, settings, torrent_name)
# Send to Sonarr
elif (isSonarr):
	log.info("Passing %s directory to Sonarr." % path)
	sonarr.processEpisode(path, settings)

if delete_dir:
	if os.path.exists(delete_dir):
		time.sleep(60)
		log.info("Will remove temporary directory.")
		try:
			shutil.rmtree(delete_dir, ignore_errors=True)
			log.debug("Successfully removed temporary directory %s." % delete_dir)
		except:
			log.exception("Unable to delete temporary directory.")

