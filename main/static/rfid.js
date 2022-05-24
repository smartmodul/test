class RfidContext{constructor(){this.createModal(),this.createButton()}createModal(){$('<div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title" id="rfidLabel"></h5></div><div class="modal-body"><div class="addLoader">Waiting for card ...<br></div><div class="addLoader spinner-grow" style="width: 3rem; height: 3rem;" role="status"></div><div id="rfidAdded"></div><div id="rfidFail"></div><form><div class="mb-2"><textarea class="form-control" id="msg"></textarea></div></form></div><div class="modal-footer"><button id="hideRFID" type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button><button id="saveRFID" type="button" class="btn btn-primary">Save</button></div></div></div>').appendTo("#rfidModal"),document.getElementById("saveRFID").addEventListener("click",function(){let d=$("#rfidLabel").text().substring(11);$("#id"+d).text($("#msg").val()),$("#rfidModal").modal("hide")}),document.getElementById("hideRFID").addEventListener("click",function(){$("#rfidModal").modal("hide")})}createButton(){$('<div id="rfid0" class="container-sm text-center mt-3 w-60"><div class="btn-group w-100" role="group"><button id="refreshRfid" type="button" class="btn btn-primary btn-outline-light"><i class="fas fa-redo fa-2x"></i></button><button id="addRfid" type="button" class="btn btn-primary btn-outline-light"><i class="fas fa-user-plus fa-2x"></i></button><button id="saveRfid" type="button" class="btn btn-primary btn-outline-light"><i class="far fa-save fa-2x"></i></button></div></div>').appendTo("#rfidBtn")}}class CreateRfidList{constructor(d){this.createRFIDList(d)}createRFID(d,t,e){$('<div id="rfid'+d+'" class="container-sm text-center mt-3 w-60"><div class="card bg-grey"><div class="row justify-content-md-center"><div class="col-4 align-self-center text-right"><i class="fas fa-id-card fa-3x"></i></div><div class="col text-left"><div id="id'+d+'" class="font-weight-bold">'+e+'</div><div style="font-size:13px;" class="font-italic">'+t+'</div></div></div><div class="btn-group" role="group"><button id="remove'+d+'" type="button" class="btn btn-dark btn-outline-light"><i class="far fa-trash-alt"></i></button><button id="edit'+d+'" type="button" class="btn btn-dark btn-outline-light"><i class="fas fa-user-edit"></i></button></div></div></div>').insertAfter("#rfid"+(d-1)),document.getElementById("remove"+d).addEventListener("click",function(){$("#rfid"+d).remove()}),document.getElementById("edit"+d).addEventListener("click",function(){$("#rfidLabel").text("Edit user: "+d),$("#msg").val(e),$("#msg").show(),$("#saveRFID").show(),$(".addLoader").hide(),$("#rfidAdded").hide(),$("#rfidFail").hide(),$("#rfidModal").modal("show")})}createRFIDList(d){console.log(d);var t=Object.keys(d);let e=[];for(let t in d)e.push(d[t]);for(var i=0;i<t.length;i++)this.createRFID(i+1,e[i],t[i])}}$(function(){const d=(d="default",t="",e="")=>{$("#rfidLabel").text(t),$("#msg").hide(),$("#saveRFID").hide(),"addOK"===d||"savedOK"===d?($(".addLoader").hide(),$("#rfidFail").hide(),$("#rfidAdded").text(e),$('<br><br><i class="fas fa-check-circle fa-3x" style="color:green;"></i>').appendTo("#rfidAdded"),$("#rfidAdded").show()):"addWaiting"===d?($(".addLoader").show(),$("#rfidFail").hide(),$("#rfidAdded").hide()):"savedNOK"!==d&&"addNOK"!==d||($(".addLoader").hide(),$("#rfidAdded").hide(),$("#rfidFail").text(e),$('<br><br><i class="fas fa-exclamation-triangle fa-3x" style="color:red;"></i>'+e).appendTo("#rfidFail"),$("#rfidFail").show()),$("#rfidModal").modal("show")};$(document).on("click","#refreshRfid",function(){for(let d=1;d<=20&&$("#rfid"+d);d++)$("#rfid"+d).remove();$.ajax({url:"/updateRFID"}).done(function(d){new CreateRfidList(d)})}),$(document).on("click","#addRfid",function(){let t=0;$.ajax({type:"POST",url:"/updateRFID",async:!0,data:JSON.stringify({addRfid:0}),success:function(t){1==t.addRfid&&d("addWaiting","Approach RFID card to the RFID reader.")},error:function(t){d("addNOK","Approach RFID card to the RFID reader.","Check rfid or network conneciton.")}}),timer=setInterval(function(){++t>2&&(d("addOK","Approach RFID card to the RFID reader.","Card added successfully!"),clearTimeout(timer))},2e3)}),$(document).on("click","#saveRfid",function(){$.ajax({type:"POST",url:"/updateRFID",async:!0,data:JSON.stringify({saveRfid:1}),success:function(t){1==t.saveRfid?d("savedOK","Save value to memory.","Value was saved successfully!"):d("savedNOK","Save value to memory.","Check rfid or network conneciton.")},error:function(t){d("savedNOK","Save value to memory.","Check rfid or network conneciton.")}})})});