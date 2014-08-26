"use strict";

var serverPrefix = ""; // set this to e.g. `http://eideticker.mozilla.org/` to serve remote data to a local server
function getResourceURL(path) {
  if (!path)
    return null;

  return serverPrefix + path;
}

function updateContent(testInfo, dashboardId, deviceId, branchId, testId, measureId, timeRange) {
  $.getJSON(getResourceURL([dashboardId, deviceId, branchId,
                            testId].join('/') + '.json'), function(dict) {
    if (!dict || !dict['testdata']) {
      $('#data-view').html(ich.noGraph({
        "title": testInfo.shortDesc,
        "errorReason": "No data for that device/test combination. :("
      }));
      return;
    }

    var testData = dict['testdata'];
    var timeRanges = [ { 'range': 7, 'label': '7 days' },
                       { 'range': 30, 'label': '30 days' },
                       { 'range': 60, 'label': '60 days' },
                       { 'range': 90, 'label': '90 days' },
                       { 'range': 0, 'label': 'All time' } ]

    // filter the data according to time range (if we're using a time range)
    timeRange = parseInt(timeRange);
    if (timeRange !== 0) {
      var minDate = (Date.now() / 1000.0) - (timeRange * 24 * 60 * 60);
      var entriesToRemove = [];
      var allProducts = Object.keys(testData);
      allProducts.forEach(function(product) {
        Object.keys(testData[product]).forEach(function(timestamp) {
          if (parseInt(timestamp) < minDate) {
            entriesToRemove.push({ 'product': product, 'timestamp': timestamp });
          }
        });
      });
      entriesToRemove.forEach(function(entry) {
        delete testData[entry.product][entry.timestamp];
      });
      allProducts.map(function(product) {
        if (Object.keys(testData[product]).length == 0) {
          delete testData[product];
        }
      });
    }

    if (Object.keys(testData).length === 0) {
      // not enough data for this time range

      $('#data-view').html(ich.noGraph({
        'title': testInfo.shortDesc,
        'errorReason': "No data in the last " + timeRange +
          " days, try choosing a larger interval above to get old data.",
        'timeRanges': timeRanges,
        'showTimeRanges': true
      }));
    } else {

      // figure out which measures could apply to this graph
      var availableMeasureIds = [];
      Object.keys(testData).forEach(function(product) {
        Object.keys(testData[product]).forEach(function(timestamp) {
          testData[product][timestamp].forEach(function(sample) {
            var measureIds = getMeasureIdsInSample(sample, overallMeasures);
            measureIds.forEach(function(measureId) {
              if (jQuery.inArray(measureId, availableMeasureIds) === -1) {
                availableMeasureIds.push(measureId);
              }
            });
          });
        });
      });

      $('#data-view').html(ich.graph({'title': testInfo.shortDesc,
                                      'measureDescription': overallMeasures[measureId].longDesc,
                                      'measures': measureDisplayList(availableMeasureIds, overallMeasures),
                                      'timeRanges': timeRanges,
                                      'showTimeRanges': true
                                     }));

      // update graph
      updateGraph(testInfo.shortDesc, testData, measureId);

      $('#measure-'+measureId).attr("selected", "true");
      $('#measure').change(function() {
        var newMeasureId = $(this).val();
        window.location.hash = '/' + [ dashboardId, deviceId, branchId, testId,
                                       newMeasureId, timeRange ].join('/');
      });
    }

    // update time range selector
    $('#time-range-' + timeRange).attr("selected", "true");
    $('#time-range').change(function() {
      var newTimeRange = $(this).val();
      window.location.hash = '/' + [ dashboardId, deviceId, branchId, testId,
                                     measureId, newTimeRange ].join('/');
    });
  });
}

function updateGraph(title, rawdata, measureId) {
  var graphdata = [];

  // get global maximum date (for baselining)
  var globalMaxDate = 0;
  Object.keys(rawdata).forEach(function(product) {
    var dates = Object.keys(rawdata[product]).map(parseTimestamp);
    globalMaxDate = Math.max(globalMaxDate, Math.max.apply(null, dates));
  });

  var products = Object.keys(rawdata).sort();
  var color = 0;
  var seriesIndex = 0;
  var pointDetailMap = {};
  products.forEach(function(product) {
    pointDetailMap[seriesIndex] = [];

    // line graph (aggregate average per day + baseline results if appropriate)
    var series = {
      label: product,
      lines: { show: true },
      points: { show: true },
      color: color,
      data: []
    };

    var lastSample;
    var lastData;
    Object.keys(rawdata[product]).sort().forEach(function(timestamp) {
      var numSamples = 0;
      var total = 0;
      rawdata[product][timestamp].forEach(function(sample) {
        lastSample = sample;
        if (sample[measureId]) {
          total += sample[measureId];
          numSamples++;
        }
      });
      lastData = [parseTimestamp(timestamp), total/numSamples];
      series.data.push(lastData);
      pointDetailMap[seriesIndex].push({ 'product': product, 'timestamp': timestamp });
    });
    // if last sample was a baseline and there's a great data, extend
    // the baseline of the graph up to today
    if (lastSample.baseline === true && lastData[0] < globalMaxDate) {
      series.data.push([globalMaxDate, lastData[1]]);
    }
    graphdata.push(series);

    color++;
    seriesIndex++;
  });

  function updateDataPointDisplay(pointDetail, date, measureName, measureValue, series) {
    var replicates = rawdata[pointDetail.product][pointDetail.timestamp];
    var firstUUID = replicates[0].uuid;

    $.getJSON(getResourceURL('metadata/' + firstUUID + '.json'), function(metadata) {
      function updateDataPoint(prevMetadata) {
        var revisionInfoList = [];
        [
          { 'title': 'Gecko Revision',
            'revisionProperty': 'revision',
            'repotype': 'hg',
            'repoURL': metadata.sourceRepo },
          { 'title': 'Gaia Revision',
            'revisionProperty': 'gaiaRevision',
            'repotype': 'github',
            'repoURL': 'https://github.com/mozilla-b2g/gaia/' },
          { 'title': 'Build Revision',
            'revisionProperty': 'buildRevision',
            'repotype': 'github',
            'repoURL': 'https://github.com/mozilla-b2g/platform_build/' }
        ].forEach(function(revisionType) {
          if (metadata[revisionType.revisionProperty]) {
            var revisionProperty = revisionType.revisionProperty;
            var revisionInfo = {
              'title': revisionType.title,
              'revision': metadata[revisionProperty].slice(0, 12) };
            if (revisionType.repotype === 'hg') {
              revisionInfo.revisionHref = revisionType.repoURL +
                "/rev/" + metadata[revisionProperty];
              if (prevMetadata && prevMetadata[revisionProperty] &&
                  prevMetadata[revisionProperty] !== metadata[revisionProperty]) {
                revisionInfo.pushlogHref = revisionType.repoURL +
                  "/pushloghtml?fromchange=" +
                  prevMetadata[revisionProperty] + "&tochange=" +
                  metadata[revisionProperty];
              }
            } else {
              revisionInfo.revisionHref = revisionType.repoURL +
                " /commit/" + metadata[revisionProperty];
              if (prevMetadata && prevMetadata[revisionProperty] &&
                  prevMetadata[revisionProperty] !== metadata[revisionProperty]) {
                revisionInfo.pushlogHref = revisionType.repoURL +
                  "compare/" + prevMetadata[revisionProperty] + "..." +
                  metadata[revisionProperty];
              }
            }
            revisionInfoList.push(revisionInfo);
          }
        });
        $('#graph-annotation').html(ich.graphDatapoint(
          { 'measureName': measureName,
            'date': getDateStr(metadata.appdate * 1000),
            'metadata': metadata,
            'revisionInfoList': revisionInfoList,
            'buildId': metadata.buildId,
            'measureValue': measureValue
          }));

        var series = {
          bars: { show: true },
          data: []
        };
        var i=0;
        replicates.forEach(function(replicate) {
          series.data.push([i, replicate[measureName]]);
          i++;
        });
        console.log(series);
        var plot = $.plot($("#datapoint-replicates"), [series], {
          xaxis: { show: false },
          grid: { clickable: true,
                  hoverable: true }
        });

        $("#datapoint-replicates").bind("plothover", function (event, pos, item) {
          $("#tooltip").remove();
          if (item) {
            showTooltip(item.pageX, item.pageY, 'Replicate #' + item.datapoint[0] + ' = ' +
                        item.datapoint[1].toFixed(2));
          }
        });

        $("#datapoint-replicates").bind("plotclick", function (event, pos, item) {
          plot.unhighlight();
          if (item) {
            var index = item.datapoint[0];
            var replicate = replicates[index];
            $.getJSON(getResourceURL('metadata/' + replicate.uuid + '.json'),
                      function(metadata) {
                        var defaultDetailParameter = getDefaultDetailParameter(
                          measureName, metadata);
                        $('#replicate-viewer').html(ich.replicateDetail({
                          'index': index,
                          'value': item.datapoint[1].toFixed(2),
                          'uuid': replicate.uuid,
                          'videoURL': getResourceURL('videos/' + replicate.uuid + '.webm'),
                          'profileURL': replicate.hasProfile ? getResourceURL('profiles/' + replicate.uuid + '.zip') : null,
                          'defaultDetailParameter': defaultDetailParameter,
                          'httpLog': metadata.httpLog ? true : false
                        }));
                        $('#replicate-viewer').show();
                        $('#video').css('width', $('#video').parent().width());
                      });
            plot.highlight(item.series, item.datapoint);
          } else {
            $('#replicate-viewer').hide();
          }
        });
      }

      // try to find the previous revision
      var prevTimestamp = null;
      Object.keys(rawdata[series.label]).sort().forEach(function(timestamp) {
        if (parseTimestamp(timestamp) < date) {
          // potential candidate
          prevTimestamp = timestamp;
        }
      });

      if (prevTimestamp) {
        var prevDayData = rawdata[series.label][prevTimestamp];
        $.getJSON(getResourceURL('metadata/' + prevDayData[0].uuid + '.json'), function(prevMetadata) {
          updateDataPoint(prevMetadata);
        });
      } else {
        updateDataPoint(null);
      }
    });
  }

  var showGraphLegend = (products.length > 1);

  function updateGraphDisplay() {
    var plot = $.plot($("#graph-container"), graphdata, {
      xaxis: {
        mode: "time",
        timeformat: "%m-%d"
      },
      yaxis: {
        axisLabel: overallMeasures[measureId].shortDesc,
        min: 0
      },
      legend: {
        show: showGraphLegend,
        position: "ne",
      },
      grid: { clickable: true, hoverable: true },
      zoom: { interactive: true },
      pan: { interactive: true }
    });

    // add zoom out button
    $('<div class="button" style="left:50px;top:20px">zoom out</div>').appendTo($("#graph-container")).click(function (e) {
      e.preventDefault();
      plot.zoomOut();
    });

    $("#graph-container").bind("plothover", function (event, pos, item) {
      $("#tooltip").remove();
      if (item) {
        var toolTip;
        var x = item.datapoint[0].toFixed(2);
        var y = item.datapoint[1].toFixed(2);
        toolTip = (item.series.label || item.series.hoverLabel) + " of " + getDateStr(item.datapoint[0]) + " = " + y;
        showTooltip(item.pageX, item.pageY, toolTip);
      }
    });

    $("#graph-container").bind("plotclick", function (event, pos, item) {
      plot.unhighlight();
      if (item) {
        var pointDetail = pointDetailMap[item.seriesIndex][item.dataIndex];
        updateDataPointDisplay(pointDetail, item.datapoint[0], measureId,
                               item.datapoint[1].toFixed(2), item.series);
        plot.highlight(item.series, item.datapoint);
      } else {
        $('#graph-annotation').html(null);
      }
    });
  }

  updateGraphDisplay();
  var redisplayTimeout = null;
  $(window).resize(function() {
    if (redisplayTimeout)
      return;
    redisplayTimeout = window.setTimeout(function() {
      redisplayTimeout = null;
      updateGraphDisplay();
      updateDataPointDisplay();
    }, 200);
  });
}

$(function() {
  var dashboards;
  var devices;
  var deviceIds;
  var currentDashboardId;

  function getTestIdForDeviceAndBranch(deviceId, branchId, preferredTest) {
    var device = devices[deviceId];
    var tests = device[branchId].tests;
    var testIds = Object.keys(tests).sort();
    var testId;
    if (preferredTest && testIds.indexOf(preferredTest) >= 0) {
      // this deviceid/branch combo has our preferred test, return it
      return preferredTest;
    } else {
      // this deviceid/branch combo *doesn't* have our preferred test,
      // fall back to the first one
      return testIds[0];
    }
  }

  function updateDashboardChooser() {
    $('#dashboard-chooser').empty();
    dashboards.forEach(function(dashboard) {
      $('<li id="dashboard-' + dashboard.id + '"><a href="' + '#/' +
        dashboard.id + '">' + dashboard.name +
        "</a></li>").appendTo($('#dashboard-chooser'));
    });
    $("#dashboard-" + currentDashboardId).addClass("active");
  }

  function updateDeviceChooser(timeRange, preferredBranchId, preferredTest) {
    $('#device-chooser').empty();

    deviceIds.forEach(function(deviceId) {
      var device = devices[deviceId];

      var branchId;
      if (preferredBranchId && device.branches.indexOf(preferredBranchId) >= 0) {
        branchId = preferredBranchId;
      } else {
        branchId = device.branches.sort()[0];
      }

      var testId = getTestIdForDeviceAndBranch(deviceId, branchId, preferredTest);
      var defaultMeasureId = device[branchId].tests[testId].defaultMeasureId;

      var deviceURL = "#/" + [ currentDashboardId, deviceId, branchId, testId, defaultMeasureId, timeRange ].join('/');
      $('<a href="' + deviceURL + '" id="device-' + deviceId + '" deviceid= ' + deviceId + ' class="list-group-item">' + devices[deviceId].name+'</a></li>').appendTo(
        $('#device-chooser'));
    });
  }

  function updateBranchChooser(timeRange, deviceId, preferredTest) {
    $('#branch-chooser').empty();

    var device = devices[deviceId];
    device.branches.forEach(function(branchId) {
      var testId = getTestIdForDeviceAndBranch(deviceId, branchId, preferredTest);
      var defaultMeasureId = device[branchId].tests[testId].defaultMeasureId;

      var url = "#/" + [ currentDashboardId, deviceId, branchId, testId, defaultMeasureId, timeRange ].join('/');
      $('<a href="' + url + '" id="branch-' + branchId + '" class="list-group-item">' + branchId +'</a></li>').appendTo(
        $('#branch-chooser'));
    });
  }

  function updateDashboard(dashboardId, cb) {
    if (currentDashboardId === dashboardId) {
      cb();
      return;
    }

    currentDashboardId = dashboardId;

    $.getJSON(getResourceURL([dashboardId, 'devices.json'].join('/')), function(deviceData) {
      devices = deviceData['devices'];

      deviceIds = Object.keys(devices).sort();

      var deviceBranchPairs = [];
      deviceIds.forEach(function(deviceId) {
        devices[deviceId].branches.forEach(function(branchId) {
          deviceBranchPairs.push([deviceId, branchId]);
        });
      });
      $.when.apply($, deviceBranchPairs.map(function(pair) {
        var deviceId = pair[0];
        var branchId = pair[1];

        return $.getJSON(getResourceURL([dashboardId, deviceId, branchId,
                                         'tests.json'].join('/')),
                         function(testData) {
                           var tests = testData['tests'];
                           if (!devices[deviceId][branchId]) {
                             devices[deviceId][branchId] = {};
                           }
                           devices[deviceId][branchId]['tests'] = tests;
                         });
      })).done(cb);
    });
  }

  $.getJSON(getResourceURL('dashboard.json'), function(dashboardData) {
    dashboards = dashboardData.dashboards.sort(function(x, y) {
      return y.id < x.id;
    });

    var routes = {
      '/:dashboardId': {
        on: function(dashboardId) {
          updateDashboard(dashboardId, function() {
            updateDashboardChooser();

            var defaultDeviceId = deviceIds[0];
            var defaultBranchId = devices[defaultDeviceId].branches[0];
            var defaultTestId = Object.keys(devices[defaultDeviceId][defaultBranchId].tests).sort()[0];
            var defaultMeasureId = devices[defaultDeviceId][defaultBranchId].tests[defaultTestId].defaultMeasureId;
            var defaultTimeRange = 7;

            window.location.hash = '/' + [ currentDashboardId, defaultDeviceId,
                                           defaultBranchId,
                                           defaultTestId,
                                           defaultMeasureId,
                                           defaultTimeRange ].join('/');
          });
        }
      },
      '/:dashboardId/:deviceId/:branchId/:testId/:measureId/:timeRange': {
        on: function(dashboardId, deviceId, branchId, testId, measureId, timeRange) {
          updateDashboard(dashboardId, function() {
            updateDashboardChooser();

            if (!devices[deviceId] || !devices[deviceId][branchId] || !devices[deviceId][branchId]['tests'][testId]) {
              $('#data-view').html("<p class='lead'>That device/branch/test/measure combination does not seem to exist. Maybe you're using an expired link? <a href=''>Reload page</a>?</p>");
              return;
            }

            updateDeviceChooser(timeRange, branchId, testId);
            updateBranchChooser(timeRange, deviceId, testId);

            // update list of tests to be consistent with those of this
            // particular device (in case it changed)
            $('#test-chooser').empty();

            var tests = devices[deviceId][branchId].tests;
            var testKeys = Object.keys(tests).sort();
            testKeys.forEach(function(testKey) {
              $('<a id="' + testKey + '" class="list-group-item">' + testKey + '</a>').appendTo($('#test-chooser'));
            });

            // update all test links to be relative to the new test or device
            $('#test-chooser').children('a').each(function() {
              var testIdAttr = $(this).attr('id');
              if (testIdAttr) {
                var defaultMeasureId = tests[testIdAttr].defaultMeasureId;
                $(this).attr('href', '#/' +
                             [ currentDashboardId, deviceId, branchId,
                               testIdAttr, defaultMeasureId,
                               timeRange ].join('/'));
              }
            });

            // highlight chosen selections in choosers
            $('#device-chooser').children('#device-'+deviceId).addClass("active");
            $('#branch-chooser').children('#branch-'+branchId.replace('.', '\\.')).addClass("active");
            $('#test-chooser').children('#'+testId).addClass("active");

            var testInfo = tests[testId];
            updateContent(testInfo, dashboardId, deviceId, branchId, testId,
                          measureId, timeRange);
          });
        }
      }
    }

    var router = Router(routes).configure({
      'notfound': function() {
        $('#data-view').html(ich.noGraph({
          "title": "Invalid URL",
          "errorReason": "Invalid or expired route (probably due to a " +
            "change in Eideticker). Try selecting a valid combination " +
            "from the menu on the left."
        }));
      }
    });

    router.init('/'+ dashboards[0].id);
  });
});
