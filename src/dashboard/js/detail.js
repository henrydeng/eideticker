"use strict";

$(function() {

  function render(metadata, measureId) {

    var measureValues = metadata[measureId];
    var actions = metadata.actionLog;

    var seriesList = [];
    var currentSeries = null;
    var lastSeries = null;
    var currentAction = null;
    var colors = [ '#f00', '#a00', '#aaa' ];
    var actionColorIndex = 0;
    var i = 0.0;
    var actionCount = {};

    var fps = metadata.fps;
    var generatedVideoFPS = metadata.generatedVideoFPS;
    if (!fps) fps = 60.0;
    if (!generatedVideoFPS) generatedVideoFPS = 60.0;

    $('#measure-'+measureId).attr("selected", "true");
    $('#measure').change(function() {
      var newMeasureId = $(this).val();
      window.location.hash = '/' + newMeasureId;
    });

    measureValues.forEach(function(diffsum) {
      // if we have a current action, check to make sure
      // we're still within it
      if (currentAction && i > currentAction.end) {
        currentAction = null;
        seriesList.push(currentSeries);
        lastSeries = currentSeries;
        currentSeries = null;
      }
      // if we don't have a current action (or just went
      // out of one) see if there's any left in the log
      // and if so, whether we're now inside one
      if (!currentAction && actions && actions.length > 0 &&
          i > actions[0].start && i < actions[0].end) {
        if (actions[0].type === "sleep") {
          // just skip sleep events as they're not very interesting
          actions.shift();
        } else {
          if (currentSeries) {
            seriesList.push(currentSeries);
            lastSeries = currentSeries;
          }
          currentAction = actions.shift();
          if (actionCount[currentAction.type] === undefined) {
            actionCount[currentAction.type] = 1;
          } else {
            actionCount[currentAction.type]++;
          }
          currentSeries = { data: [], color: colors[actionColorIndex],
                            label: currentAction.type + " " +
                            actionCount[currentAction.type] + " (time: " +
                            currentAction.start.toFixed(4) + "s - " +
                            currentAction.end.toFixed(4) +
                            "s)" };
          actionColorIndex = actionColorIndex ? 0 : 1;
        }
      }
      // if we're not in action and we have no currentSeries, create a
      // "null" grey series indicating a dead space before/between/after
      // actions
      if (currentSeries === null) {
        currentSeries = { data: [], color: colors[2] }
      }

      if (lastSeries) {
        // we keep track of the last series so the graph looks continuous
        lastSeries.data.push([ i, diffsum ]);
        lastSeries = null;
      }
      currentSeries.data.push([ i, diffsum ]);
      i+=(1.0/fps);
    });

    if (currentSeries)
      seriesList.push(currentSeries);

    var markings = [];
    var timeToStableFrame = null;
    if (metadata.metrics && metadata.metrics.timetostableframe) {
      timeToStableFrame = metadata.metrics.timetostableframe
      markings.push({ color: "#000", lineWidth: 1, xaxis: { from: timeToStableFrame, to: timeToStableFrame } });
    }

    var graphContainer = $("#graph-container");
    var plot = $.plot(graphContainer, seriesList, {
      xaxis: {
        axisLabel: "Time (seconds)"
      },
      yaxis: {
        axisLabel: perFrameMeasures[measureId].shortDesc,
        min: 0
      },
      legend: { show: false },
      grid: { clickable: true, hoverable: true, mouseActiveRadius: 1000, markings: markings },
      pan: { interactive: true }
    });

    if (timeToStableFrame) {
      var min = Math.min.apply(Math, measureValues)
      var mid = min + ((Math.max.apply(Math, measureValues) - min) / 2);
      var o = plot.pointOffset({ x: timeToStableFrame, y: mid});
      graphContainer.append("<div style='position:absolute;left:" + (o.left + 4) + "px;top:" + o.top + "px;color:#666;font-size:smaller'>Image stable</div>");
    }

    graphContainer.bind("plotclick", function (event, pos, item) {
      var video = $("#frameview").get(0);
      video.currentTime = item.datapoint[0];
    });

    var previousPoint = null;
    var currentTime = 0.0;
    var frameNum = 0;

    function datumSelected(datum, series) {
      plot.unhighlight();
      plot.highlight(series, datum);
      currentTime = datum[0];
      var videoTime = currentTime * (fps/generatedVideoFPS);
      frameNum = parseInt(currentTime * fps);

      var video = $("#frameview").get(0);
      video.currentTime = videoTime;
      $("#datapoint").html(ich.graphDatapoint({ 'time': currentTime.toFixed(8),
                                                'frameNum': frameNum,
                                                'measureName': perFrameMeasures[measureId].shortDesc,
                                                'measureValue': datum[1],
                                                'eventName': series.label }));
      var modal = $('#videoDetailModal');
      if (modal.length) {
        var largeVideo = $("#large-video").get(0);
        largeVideo.currentTime = videoTime;
        $(".modal-title").html("<h4>Frame " + frameNum + "</h4>");
      }
      updateButtons();
    }

    function updateButtons() {
      $(".btn-forward").unbind('click');
      $(".btn-back").unbind('click');

      function forward() {
        var foundElement = false;
        plot.getData().some(function(series) {
          series.data.some(function(datum) {
            if (datum[0] > currentTime) {
              datumSelected(datum, series);
              foundElement = true;
            }
            return foundElement;
          });

          return foundElement;
        });
      }

      function backward() {
        var foundElement = false;
        plot.getData().some(function(series) {
          var prevDatum = null;
          var prevSeries = null;
          series.data.some(function(datum) {
            if (prevDatum && Math.abs(datum[0] - currentTime) < 0.00001) {
              datumSelected(prevDatum, prevSeries);
              foundElement = true;
            }
            prevDatum = datum;
            prevSeries = series;
            return foundElement;
          });

          return foundElement;
        });
      }

      $(".btn-forward").click(function() {
        $(".btn-forward").blur();
        forward()
        return false;
      });

      $(".btn-back").click(function() {
        $(".btn-back").blur();
        backward()
        return false;
      });

      document.onkeydown = function(e) {
        if (e.keyCode == '37') {
          // left arrow
          backward();
        }
        else if (e.keyCode == '39') {
          // right arrow
          forward();
        }
      }
    }
    updateButtons();

    graphContainer.bind("plothover", function (event, pos, item) {
      if (item) {
        datumSelected(item.datapoint, item.series);
      }
    });
    $('#videobox').click(function() {
      $('#videoDetailModal').remove();
      $('body').after(ich.videoDetail({'title': 'Frame ' + frameNum,
                                       'videoPath': metadata.video }));
      $('#videoDetailModal').modal();
      var video = $("#large-video").get(0);
      video.addEventListener('loadedmetadata', function() { video.currentTime = currentTime; }, false);
      updateButtons();
    });
  }

  var uuid = getParameterByName('id');
  $.getJSON('metadata/' + uuid + '.json', function(metadata) {
    var title = metadata.label;
    if (!title) {
      title = "Frame difference view";
    }
    document.title = title;
    $('#header').html(ich.pageHeader({ 'title': title }));
    var availableMeasureIds = getMeasureIdsInSample(metadata, perFrameMeasures);
    var defaultMeasureId = availableMeasureIds[0]; // if none provided, any will do?

    var routes = {
      '/:measureId': {
        on: function(measureId) {
          $('#maincontent').html(ich.pageContent({ 'videoPath': 'videos/' + uuid + '.webm',
                                                   'measures': measureDisplayList(availableMeasureIds,
                                                                                  perFrameMeasures),
                                                   'measureDescription': perFrameMeasures[measureId].longDesc
                                                 }));

          render(metadata, measureId);
        }
      }
    };

    var router = Router(routes).init('/' + defaultMeasureId);
  });
});
