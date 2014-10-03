---

layout: default
key: home
title:  Open Data Index

---

{% capture historical_intro %}{% include content/historical_intro.md year="2013" %}{% endcapture %}
{{ historical_intro|markdownify }}

{% include partials/dataviews/glance.html year="2013" data_glance_class="row" data_point_class="col-md-3" %}

{% include partials/dataviews/comparative_table.html year="2013" %}

Current: <a href="{{ site.baseurl }}/" title="">Open Data Index</a>
