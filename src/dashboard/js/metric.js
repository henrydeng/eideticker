"use strict";

function updateContent(title, availableMeasureIds, measureId) {
  $('#content').html(ich.graph({'title': title,
                                'measureDescription': overallMeasures[measureId].longDesc,
                                'measures': measureDisplayList(availableMeasureIds, overallMeasures)
                               }));
  $('#measure-'+measureId).attr("selected", "true");
  $('#measure').change(function() {
    var newMeasureId = $(this).val();
    window.location.hash = '/' + newMeasureId;
  });
}

function updateGraph(rawdata, measureId) {
  // show individual data points
  var graphdata = [];
  var colorCounter = 0;
  var uuidHash = {};

  var seriesIndex = 0;
  var barPosition = 1;
  Object.keys(rawdata).sort().forEach(function(appname) {
    uuidHash[seriesIndex] = [];

    var label;
    var color = colorCounter;
    if (appname === "com.android.chrome") {
      label = "Chrome for Android";
    } else if (appname === "com.google.android.browser") {
      label = "ICS Stock Browser";
    } else if (appname === "com.opera.browser") {
      label = "Opera Browser";
    } else if (appname === "mobi.mgeek.TunnyBrowser") {
      label = "Dolphin";
    } else if (appname === "org.mozilla.firefox") {
      label = "Old Firefox Mobile";
    } else if (appname === "org.mozilla.firefox_beta") {
      label = "New Firefox Mobile Beta";
      color = "#e8780a";
    } else {
      label = appname;
    }
    // point graph
    var series = {
      label: label,
      bars: { show: true },
      color: color,
      data: []
    };
    rawdata[appname].forEach(function(sample) {
      series.data.push([ barPosition, sample[measureId] ]);
      console.log(sample.uuid);
      uuidHash[seriesIndex].push(sample.uuid);

      barPosition++;
    });
    graphdata.push(series);

    colorCounter++;
    seriesIndex++;
    barPosition++; // space between apps
  });

  var axisLabel = overallMeasures[measureId].shortDesc;

  var plot = $.plot($("#graph-container"), graphdata, {
    xaxis: { show: false },
    yaxis: {
      axisLabel: axisLabel
    },
    legend: {
      container: $("#legend"),
    },
    grid: { clickable: true, hoverable: true }
  });

  $("#graph-container").bind("plotclick", function (event, pos, item) {
    plot.unhighlight();
    if (item) {
      var uuid = uuidHash[item.seriesIndex][item.dataIndex];
      $.getJSON('metadata/' + uuid + '.json', function(metadata) {
        var defaultDetailParameter = getDefaultDetailParameter(measureId, metadata);

        $('#datapoint-info').html(ich.graphDatapoint({ 'uuid': uuid,
                                                       'date': null,
                                                       'videoURL': 'videos/' + uuid + '.webm',
                                                       'measureName': measureId,
                                                       'appDate': metadata.appDate,
                                                       'revision': metadata.revision,
                                                       'buildId': metadata.buildId,
                                                       'measureValue': Math.round(100.0*item.datapoint[1])/100.0,
                                                       'defaultDetailParameter': defaultDetailParameter
                                                     }));
        $('#video').css('width', $('#video').parent().width());
        $('#video').css('max-height', $('#graph-container').height());
      });
      plot.highlight(item.series, item.datapoint);
    } else {
      $('#datapoint-info').html(null);
    }
  });
}

$(function() {

  var dataFilename = getParameterByName('data');
  if (!dataFilename)
    dataFilename = 'metric.json';

  $.getJSON(dataFilename, function(data) {
    // figure out which measures could apply to this graph
    var availableMeasureIds = [];
    Object.keys(data['data']).forEach(function(appname) {
      data['data'][appname].forEach(function(sample) {
        var measureIds = getMeasureIdsInSample(sample, overallMeasures);
        measureIds.forEach(function(measureId) {
          if (jQuery.inArray(measureId, availableMeasureIds) === -1) {
            availableMeasureIds.push(measureId);
          }
        });
      });
    });

    var defaultMeasureId = availableMeasureIds[0];

    var router = Router({ '/:measureId': {
      on: function(measureId) {
        updateContent(data['title'], availableMeasureIds, measureId);
        updateGraph(data['data'], measureId);
      }
    } }).init('/' + defaultMeasureId);
  });
});
