import zipfile, os, tempfile, shutil, subprocess, plistlib, stat, sys

# Full path to ipa: "/path/to/app.ipa"
ipa_source = ""
# Full path to provisioning profile: "/path/to/profile.mobileprovision"
profile_source = ""
# Signing identity name for profile: "iPhone Developer: Developer Identity"
identity_name = ""
# TeamID used to update the entitlements
team_id = ""
# If needed, set to a string containing the bundle identifier to match your profile: "com.company.app"
bundle_identifier = None
# If you would like to rename the app, change this to a string
bundle_name = None 

def log(name, value):
	print '%s:\n\t%s' % (name, value)

# Create temporary directory for work
temp_dir = tempfile.mkdtemp()
log('temp_dir', temp_dir)

try:
	# Unzip IPA
	z = zipfile.ZipFile(ipa_source)
	z.extractall(temp_dir)
	z.close()

	# Find .app
	payload = os.path.join(temp_dir, 'Payload')
	log('payload', payload)
	app = None
	for item in os.listdir(payload):
		if os.path.splitext(item)[1] == '.app':
			app = os.path.join(payload, item)
			break
	log('app', app)

	# Delete current signing
	signature = os.path.join(app, '_CodeSignature')
	log('signature', signature)
	if os.path.exists(signature):
		shutil.rmtree(signature)
	resources = os.path.join(app, 'CodeResources')
	log('resources', resources)
	if os.path.exists(resources):
		shutil.rmtree(resources)

	# Replace provisioning profile
	profile = os.path.join(app, 'embedded.mobileprovision')
	log('profile', profile)
	shutil.copy2(profile_source, profile)

	# Convert plist to xml (can't edit binary)
	binaryplist = os.path.join(app, 'Info.plist')
	log('binaryplist', binaryplist)
	p = list(os.path.splitext(binaryplist))
	p[0] = p[0] + '.xml'
	xmlplist = ''.join(p)
	log('xmlplist', xmlplist)
	execute = 'plutil -convert xml1 -o "%s" "%s"' % (xmlplist, binaryplist)
	log('plutil', execute)
	subprocess.call(execute, shell=True)

	plist = plistlib.readPlist(xmlplist)
	if bundle_identifier or bundle_name:
		# Change bundle identifier and display name
		if isinstance(bundle_identifier, str) or isinstance(bundle_identifier, unicode):
			plist['CFBundleIdentifier'] = bundle_identifier
		if isinstance(bundle_name, str) or isinstance(bundle_name, unicode):
			plist['CFBundleDisplayName'] = bundle_name
		plistlib.writePlist(plist, xmlplist)

		# Convert plist back to binary and delete xml copy
		execute = 'plutil -convert binary1 -o "%s" "%s"' % (binaryplist, xmlplist)
		log('plutil', execute)
		subprocess.call(execute, shell=True)
	os.remove(xmlplist)
	bundle_identifier = plist['CFBundleIdentifier']
	bundle_name = plist['CFBundleDisplayName']

	# Fix exec permission on executable (is this needed?)
	p = os.path.splitext(os.path.basename(app))
	executable = os.path.join(app, p[0])
	log('executable', executable)
	permissions = os.stat(executable).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
	log('permissions', permissions)
	os.chmod(executable, permissions)

	# Create entitlements.plist
	entitlementsplist = {
		'application-identifier':'%s.%s' % (team_id, bundle_identifier),
		'get-task-allow':False
	}
	entitlementspath = os.path.join(temp_dir, 'entitlements.plist')
	plistlib.writePlist(entitlementsplist, entitlementspath)
	log('entitlementspath', entitlementspath)

	# Resign using 
	execute = 'codesign -f -s "%s" --entitlements "%s" --resource-rules "%s/ResourceRules.plist" "%s"' % (identity_name, entitlementspath, app, app)
	log('codesign', execute)
	process = subprocess.Popen(execute, shell=True, stderr=subprocess.PIPE)
	while True:
		out = process.stderr.read(1)
		if out == '' and process.poll() != None:
			break
		if out != '':
			sys.stdout.write(out)
			sys.stdout.flush()

	# Create new resigned .ipa file
	p = list(os.path.splitext(ipa_source))
	p[0] = p[0] + '.resigned'
	output = ''.join(p)
	log('output', output)
	z = zipfile.ZipFile(output, 'w')
	for root, dirs, files in os.walk(temp_dir):
		for name in files:
			path = os.path.join(root, name)
			z.write(path, os.path.relpath(path, temp_dir))
	z.close()
finally:
	# Clean temp folder
	shutil.rmtree(temp_dir)
	pass