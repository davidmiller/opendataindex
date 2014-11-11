define(['leaflet', 'leaflet_zoommin', 'jquery', 'pubsub', 'lodash', 'chroma', 'marked', 'data'], function(leaflet, leaflet_zoommin, $, pubsub, _, chroma, marked, data) {

    var $tools = $('.odi-vis-tools'),
        $legend = $('.odi-vis-legend ul'),
        $display = $('.odi-vis-display'),
        $infoTrigger = $('.odi-vis-show-info'),
        $infoBox = $('.odi-vis-info'),
        $infoClose = $('.odi-vis-info-close'),
        $placeBox = $('.odi-vis-place'),
        $placeClose = $('.odi-vis-place-close'),
        $datasetFilter = $tools.find('.odi-filter-dataset').first(),
        $yearFilter = $tools.find('.odi-filter-year').first(),
        $sharePanel = $('.odi-vis-share'),
        $embedPanel = $('.odi-vis-embed'),
        $helpPanel = $('.odi-vis-help'),
        topics = {
            init: 'init',
            tool_change: 'tool.change',
            state_change: 'state.change'
        },
        trueStrings = ['true', 'yes'],
        falseStrings = ['false', 'no'],
        colorLight = '#f5f5f5',
        colorDark = '#2d2d2d',
        colorSteps = ['#ff0000', '#edcf3b', '#7ab800'],
        colorScale = chroma.scale(colorSteps).domain([0, 100]),
        mapLatLongBase = [20.0, 5.0],
        mapZoomBase = 2,
        mapInitObj = {
            zoomControl: false,
            attributionControl: false,
            minZoom: 2,
            maxZoom: 4
        },
        map = leaflet.map('map', mapInitObj).setView(mapLatLongBase, mapZoomBase),
        placeControl = leaflet.control(),
        placeBoxClass = 'odi-vis-place',
        placeBoxTmpl = _.template($('script.place-box').html()),
        placeStyleBase = {
            weight: 1,
            opacity: 1,
            color: colorDark,
            dashArray: '2',
            fillOpacity: 1
        },
        placeStyleFocus = {
            weight: 1.5,
            color: colorDark,
            dashArray: '',
        },
        infoBoxTmpl = _.template($('script.info-box').html()),
        yearOptionsTmpl = _.template($('script.year-options').html()),
        datasetOptionsTmpl = _.template($('script.dataset-options').html()),
        embedCodeTmpl = _.template($('script.embed-code').html()),
        geojson,
        dataStore = {
            meta: undefined,
            summary: undefined,
            places: undefined,
            datasets: undefined,
            entries: undefined,
            geo: undefined
        },
        queryString = window.location.search,
        uiStateDefaults = {
            filter: {
                year: currentYear,
                dataset: 'all'
            },
            panel: {
                logo: true,
                name: true,
                tools: true,
                share: true,
                embed: true,
                help: true,
                legend: true,
            },
            map: {
                lat: '20.0',
                long: '5.0',
                place: undefined
            },
            asQueryString: undefined
        },
        uiState = setUIState(topics.init, getUIStateArgs());

    pubsub.subscribe(data.topics.meta, metaHandler);
    pubsub.subscribe(data.topics.summary, summaryHandler);
    pubsub.subscribe(data.topics.places, placesHandler);
    pubsub.subscribe(data.topics.datasets, datasetsHandler);
    pubsub.subscribe(data.topics.entries, entriesHandler);
    pubsub.subscribe(topics.tool_change, updateUIState);
    pubsub.subscribe(topics.state_change, redrawDisplay);
    pubsub.subscribe(topics.state_change, pushStateToURL);
    pubsub.subscribe(topics.init, setPanels);
    pubsub.subscribe(topics.state_change, setPanels);

    function metaHandler(topic, data) {
        var context = {};

        dataStore.meta = data;
        _.each(data.years, function(value) {
            context.year = value;
            if (uiState.filter.year === value) {
                context.selected = 'selected';
            } else {
                context.selected = '';
            }
            $yearFilter.append(yearOptionsTmpl(context));
        });
    }

    function summaryHandler(topic, data) {

    }

    function placesHandler(topic, data) {
        dataStore.places = data.places;
        dataStore.geo = data.geo;
        geoHandler(data.geo);
    }

    function geoHandler(data) {
        setGeoColorScale(data);
    }

    function datasetsHandler(topic, data) {
        var context = {};

        dataStore.datasets = data;
        _.each(data, function(value) {
            context.dataset_id = value.id;
            context.dataset = value.title;
            if (uiState.filter.dataset === value.id) {
                context.selected = 'selected';
            } else {
                context.selected = '';
            }
            $datasetFilter.append(datasetOptionsTmpl(context));
        });
    }

    function entriesHandler(topic, data) {
        dataStore.entries = data;
    }

    function setPanels(topic, data) {
        if (!data.panel.tools) {
            $toolsPanel.hide();
        }
        if (!data.panel.share) {
            $sharePanel.hide();
        }
        if (!data.panel.embed) {
            $embedPanel.hide();
        }
        if (!data.panel.help) {
            $helpPanel.hide();
        }
    }

    function pushStateToURL(topic, data) {
        history.pushState({}, '', data.asQueryString);
    }

    function getStateQueryString(state) {
        var qargs = [];
        _.forOwn(state, function(value, key) {
            if (key !== 'asQueryString') {
                // key namespace
                ns = 'K_'.replace('K', key);
                _.forOwn(value, function(nv, nk) {
                    // ONLY add params for non-default values
                    if (nv !== uiStateDefaults[key][nk]) {
                        // param key
                        pk = encodeURIComponent('NS_K'.replace('NS_', ns).replace('K', nk));
                        pv = encodeURIComponent(nv);
                        param = 'K=V'.replace('K', pk).replace('V', pv);
                        qargs.push(param);
                    }
                });
            }
        });
        if(qargs.length > 0){
            qs = '?QARGS'.replace('QARGS', qargs.join('&'));
        } else {
           qs = '';
        }
        return qs;
    }

    function setUIState(topic, data) {
        var rv = _.cloneDeep(uiStateDefaults);

        _.forOwn(data, function(value, key) {
            _.assign(rv[key], value);
        });
        rv.asQueryString = getStateQueryString(rv);
        return rv;
    }

    function updateUIState(topic, data) {
        uiState = setUIState(topic, getUIStateArgs(data));
        pubsub.publish(topics.state_change, uiState);
    }

    /**
     * Bootstraps the UI state from passed args.
     * Args come from query params, but if `data` is passed,
     * it overrides query params (and updates them).
     */
    function getUIStateArgs(data) {
        var cleanedQuery = queryString
                        .replace(/\?/g, '')
                        .replace(/\//g, '')
                        .split("&"),
            allowedArgs = [
                'filter_year',
                'filter_dataset',
                'panel_logo',
                'panel_name',
                'panel_tools',
                'panel_share',
                'panel_embed',
                'panel_help',
                'panel_legend',
                'map_lat',
                'map_long',
                'map_place'
            ],
            passedState = {
                filter: {},
                panel: {},
                map: {}
            };

        if (typeof(data) !== 'undefined') {
            return data;
        } else {
            _.each(cleanedQuery, function(value) {
                // get key/value from string
                kv = value.split('=');
                if (_.contains(allowedArgs, kv[0])) {
                    // get namespace args from key
                    ns = kv[0].split('_');
                    // force true/false strings to boolean values
                    if (_.contains(trueStrings, kv[1].toLowerCase())) {
                        kv[1] = true;
                    } else if (_.contains(falseStrings, kv[1].toLowerCase())) {
                        kv[1] = false;
                    }
                    passedState[ns[0]][ns[1]] = kv[1];
                }
            });
            return passedState;
        }
    }

    function setPlaceColors(feature) {
        var fillColor = colorLight,
        score = 0,
        match;

        if (uiState.filter.dataset === 'all' ||
            typeof(uiState.filter.dataset) === 'undefined') {
            // get calculated total scores from the place data
            match = _.find(dataStore.places, {'id': feature.properties.iso_a2.toLowerCase()});
            if (match) {
                score = parseInt(match.score, 10);
                fillColor = colorScale(score).hex();
            }
        } else {
            // calculate for this dataset/year/place from entries data
            match = _.find(dataStore.entries, {
                'place': feature.properties.iso_a2.toLowerCase(),
                'year': uiState.filter.year,
                'dataset': uiState.filter.dataset
            });
            if (match) {
                score = parseInt(match.score, 10);
                fillColor = colorScale(score).hex();
            }
        }
        rv = _.clone(placeStyleBase);
        rv.fillColor = fillColor;
        return rv;
    }

    function placeHoverHandler(event) {
        var layer = event.target;

        layer.setStyle(placeStyleFocus);
        if (!leaflet.Browser.ie && !leaflet.Browser.opera) {
            layer.bringToFront();
        }
    }

    function placeExitHandler(event) {
        geojson.resetStyle(event.target);
    }

    function placeClickHandler(event) {
        map.fitBounds(event.target.getBounds());
        placeControl.update(event.target.feature.properties);
    }

    function setGeoColorScale(geo) {
        geojson = leaflet.geoJson(geo, {
            style: setPlaceColors,
            onEachFeature: onEachPlace
        }).addTo(map);

    }

    function onEachPlace(feature, layer) {
        layer.on({
            mouseover: placeHoverHandler,
            mouseout: placeExitHandler,
            click: placeClickHandler
        });
    }

    function redrawDisplay(topic, data) {
        setGeoColorScale(dataStore.geo);
    }

    /**
     * Bootstraps listeners for the info panel
     */
     function initMetaInfo() {
        var $this,
            embedClass = 'odi-vis-embed',
            context = {},
            activeInfo = '_activeinfo';

        $infoClose.on('click', function() {
            console.log('BOOM');
            $infoBox.empty();
            $infoBox.hide();
        });

        $infoTrigger.on('click', function() {
            $this = $(this);
            if ($this.hasClass(activeInfo)) {
                $this.removeClass(activeInfo);
                $infoBox.empty();
                $infoBox.hide();
            } else {
                context.title = $this.data('title');
                context.text = marked($this.data('text'));
                if ($this.hasClass(embedClass)) {
                    // we want to always enforce certain
                    // state conditions on embeds, so...
                    var embedState = _.cloneDeep(uiState);
                    embedState.panel.share = false;
                    embedState.panel.embed = false;
                    embedState.panel.tools = false;
                    context.state_params = getStateQueryString(embedState);
                    context.embed_code = embedCodeTmpl(context);
                } else {
                    context.embed_code = '';
                }
                $this.siblings().removeClass(activeInfo);
                $this.addClass(activeInfo);
                $infoBox.html(infoBoxTmpl(context));
                $infoBox.show();
            }
        });
     }

    /**
     * Bootstraps visualisation tools
     */
    function initMetaTools() {
        var $this;

        $datasetFilter.on('change', function() {
            $this = $(this);
            uiState.filter.dataset = $this.val();
            uiState.filter.year = $yearFilter.val();
            pubsub.publish(topics.tool_change, uiState);
        });

        $yearFilter.on('change', function() {
            $this = $(this);
            uiState.filter.year = $this.val();
            uiState.filter.dataset = $datasetFilter.val();
            pubsub.publish(topics.tool_change, uiState);
        });
    }

    /**
     * Bootstraps visualisation legend
     */
    function initMetaLegend() {
        var $this,
            score;

        _.each($legend.find('li'), function(value) {
            $this = $(value);
            score = parseInt($this.data('score'), 10);
            $this.css('background-color', colorScale(score).hex());
        });
    }

    /**
     * Bootstraps the visualisation meta section
     */
    function initMeta() {
        initMetaTools();
        initMetaLegend();
        initMetaInfo();
    }

    /**
     * Bootstraps the visualisation place box, which displays data on places
     */
    function initViewPlaceBox() {
        placeControl.onAdd = function (map) {
            this._div = leaflet.DomUtil.create('div', placeBoxClass);
            this.update();
            return this._div;
        };

        placeControl.update = function (properties) {
            var context = {},
                match;

            if (properties) {
                match = _.find(dataStore.places, {'id': properties.iso_a2.toLowerCase()});
                context.year = '2014';
                context.name = match.name;
                context.slug = match.id;
                context.score = parseInt(match.score, 10);
                context.rank = parseInt(match.rank, 10);
                context.improvement_phrase = 'an improvment on';
                context.previous_score = '50';
                $placeBox.html(placeBoxTmpl(context));
                $placeBox.show();
            }
        };
    }

    /**
     * Bootstraps the visualisation map
     */
    function initViewMap() {
        new L.Control.ZoomMin({ position: 'bottomright' }).addTo(map);
    }

    /**
     * Bootstraps the visualisation view section
     */
    function initView() {
        initViewMap();
        initViewPlaceBox();
    }

    /**
     * Boostraps the visualisation interface
     */
    function initUI() {
        initMeta();
        initView();
        pubsub.publish(topics.init, uiState);
    }

    return {
        init: initUI
    };
});
