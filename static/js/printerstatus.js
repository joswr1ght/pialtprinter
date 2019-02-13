function getstatus() {
    if (window.XMLHttpRequest) {
        xmlhttp=new XMLHttpRequest();
    } else {    // IE6, IE5
        xmlhttp=new ActiveXObject("Microsoft.XMLHTTP");
    }
    xmlhttp.onreadystatechange=function() {
        if (xmlhttp.readyState==4 && xmlhttp.status==200) {
            remaining = JSON.parse(xmlhttp.responseText);
            document.getElementById("printerstatus").innerHTML=remaining.printerstatus;
            return;
        }
    }
    xmlhttp.open("GET", "printerstatus", true);
    xmlhttp.send();
}

function updatepage() {
    console.log("Running updatepage()")
    var updatestatus = setInterval(getstatus, 3000);
}