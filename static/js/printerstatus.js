function getstatus() {
    if (window.XMLHttpRequest) {
        xmlhttp=new XMLHttpRequest();
    } else {    // IE6, IE5
        xmlhttp=new ActiveXObject("Microsoft.XMLHTTP");
    }
    xmlhttp.onreadystatechange=function() {
        if (xmlhttp.readyState==4 && xmlhttp.status==200) {
            [remaining, temperature, targettemperature, humidity] = JSON.parse(xmlhttp.responseText);
            document.getElementById("printerstatus").innerHTML=remaining.printerstatus;
            console.log(JSON.parse(xmlhttp.responseText));
            document.getElementById("spantemperature").innerHTML=temperature;
            document.getElementById("spantargettemperature").innerHTML=targettemperature;
            document.getElementById("spanhumidity").innerHTML=humidity;
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
