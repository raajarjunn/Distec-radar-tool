# apps/technology/urls.py
from django.urls import path
from .views import (
    TechnologyListView, TechnologyDetailView,
    TechnologyCreateView, TechnologyUpdateView, TechnologyDeleteView,
     mindmap_view,generate_report, scorecard_compendium,
    api_macros, api_meso1, api_meso2, api_techs,
    add_extra_field, edit_extra_field, delete_extra_field,
    add_gallery_image, update_gallery_tag, delete_gallery_image,
    evaluate, save_chart_image, export_excel,
)



urlpatterns = [
    path("",                     TechnologyListView.as_view(),   name="technology_list"),
    path("create/",              TechnologyCreateView.as_view(), name="technology_create"),
    path("<int:pk>/",            TechnologyDetailView.as_view(), name="technology_detail"),
    path("<int:pk>/edit/",       TechnologyUpdateView.as_view(), name="technology_update"),
    path("<int:pk>/delete/",     TechnologyDeleteView.as_view(), name="technology_delete"),

  
    path("api/macros/",                  api_macros, name="tech_api_macros"),
    path("api/meso1/<str:macro>/",       api_meso1,  name="tech_api_meso1"),
    path("api/meso2/<str:meso1>/",       api_meso2,  name="tech_api_meso2"),

    path("<int:pk>/field/add/",                add_extra_field,   name="technology_add_field"),
    path("<int:pk>/field/<int:index>/edit/",   edit_extra_field,  name="technology_edit_field"),
    path("<int:pk>/field/<int:index>/delete/", delete_extra_field, name="technology_delete_field"),

    path("<int:pk>/gallery/add/",    add_gallery_image,     name="technology_gallery_add"),
    path("<int:pk>/gallery/tag/",    update_gallery_tag,    name="technology_gallery_update_tag"),
    path("<int:pk>/gallery/delete/", delete_gallery_image,  name="technology_gallery_delete"),

    path("mindmap/", mindmap_view, name="mindmap"),

    path("<int:pk>/evaluate/", evaluate, name="technology_evaluate"),
    path("<int:pk>/save_chart_image/", save_chart_image, name="technology_save_chart_image"),
    path("<int:pk>/export_excel/", export_excel, name="export_excel"),

    path("<int:pk>/scorecard/", generate_report, name="technology_scorecard"),
    path("api/techs/", api_techs, name="technology_api_techs"),
    path("scorecards/build/", scorecard_compendium, name="technology_scorecard_compendium"),
 

]
