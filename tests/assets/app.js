/// <reference path="./Clock.ts" />
var Clock;
(function (Clock) {
    var App = (function () {
        function App(element) {
            this.element = element;
            this.element.innerHTML += "The time is: ";
            this.span = document.createElement('span');
            this.element.appendChild(this.span);
            this.span.innerText = new Date().toUTCString();
            var clockDiv = document.createElement("div");
            element.appendChild(clockDiv);
            this.clock = new Clock.ClockFace(clockDiv);
        }
        App.prototype.start = function () {
            var _this = this;
            this.timerToken = setInterval(function () { return _this.span.innerHTML = new Date().toUTCString(); }, 1000);
        };
        App.prototype.stop = function () {
            clearTimeout(this.timerToken);
        };
        return App;
    })();
    Clock.App = App;
})(Clock || (Clock = {}));
window.onload = function () {
    var el = document.getElementById('content');
    var greeter = new Clock.App(el);
    greeter.start();
};
// Newline after map here to check we strip()
//# sourceMappingURL=app.js.map
