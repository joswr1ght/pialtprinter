if [ "z"$1 = "zprod" ] ; then
    rsync -ave ssh --delete --exclude='.git/' . piprintprod:pialtprinter/
else
    rsync -ave ssh --delete --exclude='.git/' . piprint:pialtprinter/
fi
