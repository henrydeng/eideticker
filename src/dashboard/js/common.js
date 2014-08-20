// various utility functions used by all eideticker web interface pages

function getParameterByName(name) {
  var match = RegExp('[?&]' + name + '=([^&]*)').exec(window.location.search);
  if (!match)
    return null;
  
  return decodeURIComponent(match[1].replace(/\+/g, ' ')).replace(
      /[\"\']/g, ' ');
}

function parseDate(datestr) {
  var parsed = datestr.split("-");
  var year = parsed[0];
  var month = parsed[1] - 1; //Javascript months index from 0 instead of 1
  var day = parsed[2];

  return Date.UTC(year, month, day);
}

function parseTimestamp(timestamp) {
  return new Date(timestamp*1000);
}

function getDateStr(timestamp) {
  var date = new Date(parseInt(timestamp));
  return date.toUTCString();
}

var overallMeasures = {
  'checkerboard': { 'shortDesc': 'Checkerboard',
                    'longDesc': 'The measure is the sum of the percentages of frames that are checkerboarded over the entire capture. Lower values are better.' },
  'uniqueframes': { 'shortDesc': 'Unique frames',
                    'longDesc': 'The measure is a calculation of the average number of UNIQUE frames per second of capture. The theoretical maximum is 60 fps (which is what we are capturing), but note that if there periods where the page being captured is unchanging this number may be aritifically low.' },
  'fps': { 'shortDesc': 'Frames per second',
           'longDesc': 'The measure is a calculation of the average number of UNIQUE frames per second of capture. The theoretical maximum is 60 fps (which is what we are capturing), but note that if there periods where the page being captured is unchanging this number may be aritifically low.' },
  'timetostableframe': { 'shortDesc': 'Time to first stable frame (seconds)',
                         'longDesc': 'The time to the first frame of the capture where the image is stable (i.e. mostly unchanging). This is a startup metric that indicates roughly when things have stopped loading. Lower values are better.' },
  'timetoresponse': { 'shortDesc': 'Time to visible response (seconds)',
                      'longDesc': 'Time between event being first sent to device and an observable response. A long pause may indicate that the application is unresponsive.' },
  'overallentropy': { 'shortDesc': 'Overall entropy over length of capture',
                      'longDesc': 'Overall information content in frames of capture. Low values may indicate that some areas of the screen were left blank while the screen was redrawing. Higher values are generally better.' }
};

var perFrameMeasures = {
  'framediffsums': { 'shortDesc': 'Frame difference (pixels)',
                     'longDesc': 'Number of pixels different between frames (low differences filtered out)'
                     },
  'framecannyentropies': { 'shortDesc': 'Frame entropy (canny)',
                           'longDesc': 'Amount of entropy in each frame, after running canny edge detection on it. Higher values indicate more information in the frame. Lower values may indicate checkerboarding.'
                         },
  'framesobelentropies': { 'shortDesc': 'Frame entropy (sobel)',
                           'longDesc': 'Amount of entropy in each frame, after running sobel edge detection on it. Higher values indicate more information in the frame. Lower values may indicate checkerboarding.'
                           }

};

function getMeasureIdsInSample(sample, measures) {
  var measuresInSample = [];
  Object.keys(measures).forEach(function(measureId) {
    if (jQuery.inArray(measureId, Object.keys(sample)) !== -1) {
      measuresInSample.push(measureId);
    }
  });

  return measuresInSample;
}

function measureDisplayList(measureIds, measures) {
  return measureIds.map(function(measureId) {
    return { 'id': measureId,
             'desc': measures[measureId].shortDesc
           };
  });
}

// default value for detail view: usually frame diff sums, unless we're
// looking at entropy, in which case we'll look at the entropy values
function getDefaultDetailParameter(measureName, metadata) {
  if (measureName === "overallentropy" && metadata.framecannyentropies) {
    return "framecannyentropies";
  } else if (measureName === "overallentropy" && metadata.framesobelentropies) {
    return "framesobelentropies";
  } else if (metadata.framediffsums) {
    return "framediffsums";
  }

  // we don't have anything to display! (old data most likely)
  return null;
}

function showTooltip(x, y, contents) {
  $('<div id="tooltip">' + contents + '</div>').css( {
    position: 'absolute',
    display: 'none',
    top: y + 5,
    left: x + 5,
    border: '1px solid #fdd',
    padding: '2px',
    'background-color': '#fee',
    opacity: 0.80
  }).appendTo("body").fadeIn(200);
}
