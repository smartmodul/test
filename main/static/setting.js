var setting={t:"undefined",n:0,refreshSetting(){$.ajax({url:"/updateSetting"}).done(function(b){for(var a in t=b,b)b.hasOwnProperty(a)&&"txt"==(a=a.split(","))[0]&&$('<div class="row  mt-3" >  <div class="col" >  <p id="debug">'+a[1]+'</p> </div>  <div class="col">  <p> '+("1"==b["sw,TESTING SOFTWARE"]?"tst_"+b[a[0]+","+a[1]]:b[a[0]+","+a[1]])+"</p> </div> </div>").appendTo("#settingTable");for(var a in $("#updateSetting").html(b.datalayer),b)if(b.hasOwnProperty(a)&&"sw"==(a=a.split(","))[0]){if("TESTING SOFTWARE"==a[1]&&"0"==b[a[0]+","+a[1]])continue;$('<div class="row  mt-4">  <div class="col" >  <p>'+a[1]+'</p> </div>  <div class="col">  <input id="'+a[1]+'"  type="checkbox" name="btn-checkbox" data-toggle="witchbutton"> </div> </div>').appendTo("#settingTable"),"1"==b[a[0]+","+a[1]]?document.getElementById(a[1]).switchButton("on",!0):document.getElementById(a[1]).switchButton("off",!1)}for(var a in b)b.hasOwnProperty(a)&&"bt"==(a=a.split(","))[0]&&$('<div class="row  mt-4 mb-3" >  <div class="col" >  <p id="'+a[1]+'">'+a[1]+'</p> </div>  <div class="col"> <button  id="resetEsp" type="button" class="btn btn-danger">RESET</button>  </div> </div>').appendTo("#settingTable");for(var a in $('.switch input[type="checkbox"]').on("change",function(){setting.saveSetting("sw,"+$(this).attr("id"),1==$(this).prop("checked")?1:0)}),$("#updateSetting").html(b.datalayer),b)b.hasOwnProperty(a)&&"in"==(a=a.split(","))[0]&&$('<div class="row mt-4"><div class="col align-self-center"><p>'+a[1]+'</p></div></div><div class="row"><div class="col"><div class="input-group" style="display: block; margin:auto;"><span class="input-group-btn"><button id="'+a[0]+","+a[1]+'" class="btnF btn-primary btn-minuse" type="button">-</button></span><input id="'+a[0]+a[1]+'"type="text" class="add-color text-center height-25" maxlength="3" size="8" value="'+b[a[0]+","+a[1]]+'"><span class="input-group-btn"><button  id="'+a[0]+","+a[1]+'" class="btnF btn-primary btn-plus" type="button">+</button> </span></div></div></div></div><div class="container mt-2"><div class="row"> <button  style="margin:auto" id="'+a[0]+","+a[1]+'" type="button" class="btnF btn-light btn-s saveValue">SAVE</button>  </div></div>').appendTo("#settingTable");$('<div id="settingResult" class="container">').appendTo("#settingTable"),setting.checkUpdate(b["txt,ACTUAL SW VERSION"],b["sw,TESTING SOFTWARE"])})},refreshWifiClient(){setTimeout(function(){$(".loader").hide(100)},6e3),$.ajax({url:"/updateWificlient",async:!0,success(b){for(var a in $("#wifiStatus").html(""),$("#ssid").empty(),$("#updateWificlient").html(b.datalayer),b)"connectSSID"==a?"None"==b[a]?($("#wifiStatus").text("Not connected to wifi"),$("#wifiStatus").css("color","#FF0000")):($("#wifiStatus").text("Currently connected to: "+b[a]),$("#wifiStatus").css("color","#74DF00")):b.hasOwnProperty(a)&&(e=b[a]<= -100?0:-50<=b[a]?100:2*(b[a]+100),$('<input type="radio" style="text-align:left;" name="ssid" value="'+a+'">'+a+": "+e+"%<br>").appendTo("#ssid"));$("#refreshSSID").find("span").remove(),$(".loader").hide(100)},error(a){$("#wifiStatus").text("Error during loading WiFi clients"),$("#wifiStatus").css("color","#FF0000"),$(".loader").hide(100),$("#refreshSSID").find("span").remove()}})},resetCounter(){0!=setting.n&&($("#resetEsp").text("WAITING "+setting.n+"s"),setting.n-=1)},checkUpdate(a,c){var b,d=parseFloat(a.substr(a.length-5,a.length));b="1"==c?"https://api.github.com/repos/smartmodul/test/contents/":"https://api.github.com/repos/smartmodul/production/contents/",$.ajax({url:b}).done(function(a){for(var b in a)(a[b].name.includes("tst")||a[b].name.includes("rev"))&&(sf=parseFloat(a[b].name.substr(a[b].name.length-5,a[b].name.length)))!=d&&($("#stat").text("New FW version is "+sf),$("#stat").css("color","red"),$("#val").text("Your FW is out of date. Enable automatic update and reset IoTMeter."),$("#myModal").modal("show"))})},saveSetting(b,a){$("#val").text(""),$("#stat").text("WAITING.. "),$("#stat").append('<span class="spinner-border spinner-border-sm"></span>'),$("#stat").css("color","black"),$("#myModal").modal("show"),isNaN(a)?($("#stat").text("VARIABLE IS NOT NUMBER"),$("#stat").css("color","red")):$.ajax({type:"POST",url:"/updateSetting",async:!0,data:JSON.stringify({variable:b,value:a}),success:function(c){$("#updateSetting").html(c.datalayer),1==c.process?($("#val").text(b.split(",")[1]+" = "+a),$("#stat").text("SAVED SUCCESS!"),$("#stat").css("color","green")):($("#val").text(b.split(",")[1]+" = "+a),$("#stat").text("SAVED UNSUCCESS!"),$("#stat").css("color","red"))}})},modbusProccess(d,a,b,c){$("#modbusStatus").text(""),"read"==b?($("#modbusStatus").text("Reading register: "+a+" ..."),$("#readReg").append('<span class="spinner-border spinner-border-sm"></span>'),$("#modbusStatus").css("color","#FBD428")):"write"==b&&($("#modbusStatus").text("Writing register: "+a+" with value: "+c+" ..."),$("#writeReg").append('<span class="spinner-border spinner-border-sm"></span>'),$("#modbusStatus").css("color","#FBD428")),isNaN(a&&d&&c)?($("#modbusStatus").text("VARIABLE IS NOT NUMBER"),$("#modbusStatus").css("color","red"),$("#readReg").find("span").remove(),$("#writeReg").find("span").remove()):$.ajax({type:"POST",url:"/modbusRW",async:!0,data:JSON.stringify({type:b,id:d,reg:a,value:c}),success:function(a){$("#modbusRW").html(a.datalayer),1==a.process?($("#modbusStatus").text("Proccess successful"),$("#valueM").val(a.value),$("#modbusStatus").css("color","#74DF00"),$("#readReg").find("span").remove(),$("#writeReg").find("span").remove()):($("#modbusStatus").text("Proccess unsuccessful: "+a.value),$("#modbusStatus").css("color","red"),$("#readReg").find("span").remove(),$("#writeReg").find("span").remove())},error:function(){$("#modbusStatus").text("Response error"),$("#modbusStatus").css("color","red"),$("#writeReg").find("span").remove(),$("#readReg").find("span").remove()}})}};$(function(){$(document).on("click","#setSSID",function(){$("#setSSID").append('<span class="spinner-border spinner-border-sm"></span>'),$("#wifiStatus").html("Waiting .... "),$("#wifiStatus").css("color","#FBD428"),password=$("#passwordField").val();var a=$("input[name='ssid']:checked").val();a?$.ajax({type:"POST",url:"/updateWificlient",async:!0,data:JSON.stringify({ssid:a,password:password}),success:function(b){$("#updateWificlient").html(b.datalayer),0==b.process?($("#wifiStatus").html("Please choose ssid client first!"),$("#wifiStatus").css("color","#FF0000")):1==b.process?($("#wifiStatus").html("Can not connect to Wattmeter SSID"),$("#wifiStatus").css("color","#FF0000")):2==b.process||3==b.process?($("#wifiStatus").html("Currently connected to: "+a),$("#wifiStatus").css("color","#74DF00")):($("#wifiStatus").html("Error during connection to: "+a),$("#wifiStatus").css("color","#FF0000"))}}):($("#wifiStatus").html("Please choose ssid client first!"),$("#wifiStatus").css("color","#FF0000")),$("#setSSID").find("span").remove()}),$(document).on("click","#refreshSSID",function(){$("#wifiStatus").text("Scanning wifi ...."),$("#refreshSSID").append('<span class="spinner-border spinner-border-sm"></span>'),setting.refreshWifiClient()}),$(document).on("click",".btnF",function(){var a=this.id.replace(",",""),b=$("#"+this.id.replace(",","")).val();hodnota=0,$(this).hasClass("saveValue")&&setting.saveSetting(this.id,b),$(this).hasClass("btn-minuse")&&("inEVSE MAX CURRENT A"==a&&(parseInt(b)-1<0?(hodnota=0,$("#"+a).val(0)):(hodnota=parseInt(b)-1,$("#"+a).val(hodnota))),"inTIME-ZONE"==a&&(parseInt(b)-1< -24?(hodnota=-24,$("#"+a).val(-24)):(hodnota=parseInt(b)-1,$("#"+a).val(hodnota))),a.includes("inpEVSE")&&(parseInt(b)-1<0?(hodnota=0,$("#"+a).val(0)):(hodnota=parseInt(b)-1,$("#"+a).val(hodnota)))),$(this).hasClass("btn-plus")&&("inEVSE MAX CURRENT A"==a&&(parseInt(b)+1>125?(hodnota=125,$("#"+a).val(125)):(hodnota=parseInt(b)+1,$("#"+a).val(hodnota))),"inTIME-ZONE"==a&&(parseInt(b)+1>24?(hodnota=24,$("#"+a).val(24)):(hodnota=parseInt(b)+1,$("#"+a).val(hodnota))),a.includes("inpEVSE")&&(parseInt(b)+1>99?(hodnota=99,$("#"+a).val(99)):(hodnota=parseInt(b)+1,$("#"+a).val(hodnota))))}),$(document).on("click","#debug",function(){t+=1,setTimeout(function(){t=0},1e4),t>20&&($(".modal-body").text("Please reset wattmeter to switch testing FW"),$("#myModal").modal("show"),setting.saveSetting("sw,TESTING SOFTWARE",1))}),$(document).on("click","#readReg",function(){setting.modbusProccess($("#id").val(),$("#register").val(),"read",0)}),$(document).on("click","#writeReg",function(){setting.modbusProccess($("#id").val(),$("#register").val(),"write",$("#valueM").val())}),$(document).on("click","#resetEsp",function(a){setting.n=80,setInterval(setting.resetCounter,1e3),setTimeout(function(){location.reload(!0),setting.n=0,$("#resetEsp").text("FINISHING")},7e4),setting.saveSetting("bt,RESET WATTMETER",1)})})