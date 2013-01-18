#!/usr/bin/env node
var WebSocketClient = require('websocket').client;

var client = new WebSocketClient();

client.on('connectFailed', function(error) {
    console.log('Connect Error: ' + error.toString());
});

client.on('connect', function(connection) {
    console.log('WebSocket client connected');
    connection.on('error', function(error) {
        console.log("Connection Error: " + error.toString());
    });
    connection.on('close', function() {
        console.log('echo-protocol Connection Closed');
    });
    connection.on('message', function(message) {
        if (message.type === 'utf8') {
            var message = JSON.parse(message.utf8Data);
            switch(message.method)
            {
                case 'Console.messageAdded':
                    if(message.params.message.parameters)
                    {
                        var consoleStringArray = [];
                        message.params.message.parameters.forEach(function(param){
                            consoleStringArray.push(param.value);
                        });
                        console.log(consoleStringArray.join(' '));
                    }
                break;
            }
        }
    });

    function sendNumber() {
        if (connection.connected) {
            connection.sendUTF(JSON.stringify({id: 0, method: "Console.enable"}));
        }
    }
    sendNumber();
});

client.connect('ws://127.0.0.1:9222/devtools/page/138_1');