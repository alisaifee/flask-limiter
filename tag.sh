#!/bin/bash 
echo current version:$(python setup.py --version)
read -p "new version:" new_version
last_portion=$(grep -E "^History$" HISTORY.rst -5 | grep -E "^\d+.\d+.\d+")
changelog_file=/var/tmp/flask-ratelimit.newchangelog
new_changelog_heading="${new_version} `date +"%Y-%m-%d"`"
new_changelog_heading_sep=$(python -c "print '-'*len('$new_changelog_heading')")
echo $new_changelog_heading > $changelog_file
echo $new_changelog_heading_sep >> $changelog_file
python -c "print open('HISTORY.rst').read().replace('$last_portion', open('$changelog_file').read() +'\n' +  '$last_portion')" > HISTORY.rst.new 
cp HISTORY.rst.new HISTORY.rst 
vim HISTORY.rst
if rst2html.py HISTORY.rst > /dev/null 
then
    echo "tagging $new_version"
    git add HISTORY.rst 
    git commit -m "updating changelog for  ${new_version}"
    git tag -s ${new_version} -m "tagging version ${new_version}"
    python setup.py build sdist bdist_egg upload
else
    echo changelog has errors. skipping tag. 
fi;


