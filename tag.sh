#!/bin/bash
last_tag=$(git tag | sort -nr | head -n 1)
echo current version:$(python setup.py --version), current tag: $last_tag
read -p "new version:" new_version
last_portion=$(grep -P "^Changelog$" HISTORY.rst -5 | grep -P "^v\d+.\d+")
changelog_file=/var/tmp/flask-limiter.newchangelog
new_changelog_heading="v${new_version}"
new_changelog_heading_sep=$(python -c "print('-'*len('$new_changelog_heading'))")
echo $new_changelog_heading > $changelog_file
echo $new_changelog_heading_sep >> $changelog_file
echo "Release Date: `date +"%Y-%m-%d"`" >> $changelog_file
python -c "print(open('HISTORY.rst').read().replace('$last_portion', open('$changelog_file').read() +'\n' +  '$last_portion'))" > HISTORY.rst.new
cp HISTORY.rst.new HISTORY.rst
vim -O HISTORY.rst <(echo \# vim:filetype=git;git log $last_tag..HEAD --format='* %s (%h)%n%b' | sed -E '/^\*/! s/(.*)/    \1/g')
if rst2html.py HISTORY.rst > /dev/null
then
    echo "Tag $new_version"
    git add HISTORY.rst
    git commit -m "Update changelog for  ${new_version}"
    git tag -s ${new_version} -m "Tag version ${new_version}"
    rm HISTORY.rst.new
else
    echo changelog has errors. skipping tag.
fi;

