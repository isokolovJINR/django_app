from django.contrib.auth.models import User
from django.shortcuts import render
from django.views.generic.list import ListView
from .models import Course, Folder, TreeItem, Document
from groups_manager.models import Group, GroupMemberRole, Member
from django.forms.models import modelform_factory
from django.apps import apps
from .models import Module, Content
from django.urls import reverse_lazy
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, \
    PermissionRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.views.generic.base import TemplateResponseMixin, View
from .forms import ModuleFormSet, FolderCreateForm, DocumentCreateForm
from braces.views import CsrfExemptMixin, JsonRequestResponseMixin
# Create your views here.
import logging
import pdb
import json
from mptt.templatetags.mptt_tags import cache_tree_children
from django.templatetags.static import static
from guardian.core import ObjectPermissionChecker


# Get an instance of a logger
logger = logging.getLogger(__name__)


class ModuleOrderView(CsrfExemptMixin,
                      JsonRequestResponseMixin,
                      View):
    def post(self, request):
        for id, order in self.request_json.items():
            Module.objects.filter(id=id,
                                  course__owner=request.user.update(order=order))
            return self.render_json_response({'saved': 'OK'})


class ContentOrderView(CsrfExemptMixin,
                       JsonRequestResponseMixin,
                       View):
    def post(self, request):
        for id, order in self.request_json.items():
            Content.objects.filter(id=id,
                                   module__course__owner=request.user).update(order=order)
            return self.render_json_response({'saved': 'OK'})


class ContentCreateUpdateView(TemplateResponseMixin, View):
    module = None
    model = None
    obj = None
    template_name = 'courses/manage/content/form.html'

    def get_model(self, model_name):
        if model_name in ['text', 'video', 'image', 'file']:
            return apps.get_model(app_label='courses',
                                  model_name=model_name)
        return None

    def get_form(self, model, *args, **kwargs):
        Form = modelform_factory(model, exclude=['owner',
                                                 'order',
                                                 'created',
                                                 'updated'])
        return Form(*args, **kwargs)

    def dispatch(self, request, module_id, model_name, id=None):
        self.module = get_object_or_404(Module,
                                        id=module_id,
                                        course__owner=request.user)
        self.model = self.get_model(model_name)
        if id:
            self.obj = get_object_or_404(self.model,
                                         id=id,
                                         owner=request.user)
        return super().dispatch(request, module_id, model_name, id)

    def get(self, request, module_id, model_name, id=None):
        form = self.get_form(self.model, instance=self.obj)
        return self.render_to_response({'form': form,
                                        'object': self.obj})

    def post(self, request, module_id, model_name, id=None):
        form = self.get_form(self.model,
                             instance=self.obj,
                             data=request.POST,
                             files=request.FILES)

        if form.is_valid():
            obj = form.save(commit=False)
            obj.owner = request.user
            obj.save()
            if not id:
                # new content
                Content.objects.create(module=self.module,
                                       item=obj)
            return redirect('module_content_list', self.module.id)
        return self.render_to_response({'form': form,
                                        'object': self.obj})


class ModuleContentListView(TemplateResponseMixin, View):
    template_name = 'courses/manage/module/content_list.html'

    def get(self, request, module_id):
        module = get_object_or_404(Module,
                                   id=module_id,
                                   course__owner=request.user)
        return self.render_to_response({'module': module})


class ContentDeleteView(View):

    def post(self, request, id):
        content = get_object_or_404(Content,
                                    id=id,
                                    module__course__owner=request.user)
        module = content.module
        content.item.delete()
        content.delete()
        return redirect('module_content_list', module.id)


class CourseModuleUpdateView(TemplateResponseMixin, View):
    template_name = 'courses/manage/module/formset.html'
    course = None

    def get_formset(self, data=None):
        return ModuleFormSet(instance=self.course,
                             data=data)

    def dispatch(self, request, pk):
        self.course = get_object_or_404(Course,
                                        id=pk,
                                        owner=request.user)
        return super().dispatch(request, pk)

    def get(self, request, *args, **kwargs):
        formset = self.get_formset()
        return self.render_to_response({'course': self.course,
                                        'formset': formset})

    def post(self, request, *args, **kwargs):
        formset = self.get_formset(data=request.POST)
        if formset.is_valid():
            formset.save()
            return redirect('manage_course_list')
        return self.render_to_response({'course': self.course,
                                        'formset': formset})


class OwnerMixin(object):
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(owner=self.request.user)
    

class OwnerEditMixin(object):
    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class OwnerCourseMixin(OwnerMixin,
                       LoginRequiredMixin,
                       PermissionRequiredMixin):
    model = Course
    fields = ['subject', 'title', 'slug', 'overview']
    success_url = reverse_lazy('manage_course_list')


class OwnerCourseEditMixin(OwnerCourseMixin, OwnerEditMixin):
    template_name = 'courses/manage/course/form.html'


class ManageCourseListView(OwnerCourseMixin, OwnerMixin):
    template_name = 'courses/manage/course/list.html'
    permission_required = 'courses.view_course'


class CourseCreateView(OwnerCourseEditMixin, CreateView):
    permission_required = 'courses.add_course'


class CourseUpdateView(OwnerCourseEditMixin, UpdateView):
    permission_required = 'courses.change_course'


class CourseDeleteView(OwnerCourseMixin, DeleteView):
    template_name = 'courses/manage/course/delete.html'
    permission_required = 'courses.delete_course'


class ManageCourseListView(ListView):
    model = Course
    template_name = 'courses/manage/course/list.html'

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(owner=self.request.user)


###############################################################
#Функция по проходу по дереву

def get_treeitem_type(item):
    match item:
        case "document":
            return static('img/doc.png')
        case "folder":
            return static('img/folder.png')
        case _:
            return ''

def recursive_node_to_dict(node, checker, permission):

    if checker.has_perm(permission, node):
        result = {
            'id': node.pk,
            'name': str(node.content_object),
            "text": str(node.content_object),
            "icon": get_treeitem_type(node.content_type.name)
        }

        children = [recursive_node_to_dict(c, checker, permission) for c in node.get_children() if checker.has_perm(permission, c)]
        if children:
            result['children'] = children
        return result

class FolderListView(TemplateResponseMixin, View):
    model = Folder
    template_name = 'folders/manage/folder/folder_list.html'

    def get(self, request):
        TreeItem._tree_manager.rebuild()

        folders = TreeItem.objects.all()

        cur = Member.objects.get(django_user_id=request.user.id)
        print(cur.groups_manager_group_set.all())
        group = Group.objects.get(id=3)
        folder = TreeItem.objects.get(id=3)
        custom_permissions = {
            'owner': {
                'Editor': ['change'],
                'Viewer': ['delete'],
                'default': ['view'],
            },
            'group': ['view', 'add', 'change'],
            'groups_upstream': [],
            'groups_downstream': [],
            'groups_siblings': [],
        }
        # group.assign_object(folder, custom_permissions=custom_permissions)

        # pdb.set_trace()
        # cur.assign_object(group, folder, custom_permissions=custom_permissions)

        permission_checker = ObjectPermissionChecker(request.user)
        root_nodes = cache_tree_children(folders)
        dicts = []
        for n in root_nodes:
            dicts.append(recursive_node_to_dict(n, permission_checker, 'view_treeitem'))
        js = json.dumps(dicts)

        # pdb.set_trace()
        return self.render_to_response({'folders': folders, 'groups': cur.groups_manager_group_set, 'js': js})


class FolderCreateUpdateView(TemplateResponseMixin, View):
    module = None
    model = None
    obj = None
    template_name = 'folders/manage/folder/form.html'
    # def get_model(self, model_name):
    #     if model_name in ['text', 'video', 'image', 'file']:
    #         return apps.get_model(app_label='courses',
    #                               model_name=model_name)
    #     return None
    # def get_form(self, model, *args, **kwargs):
    #     Form = modelform_factory(model, exclude=['owner',
    #                                              'order',
    #                                              'created',
    #                                              'updated'])
    #     return Form(*args, **kwargs)

    # def dispatch(self, request, module_id, model_name, id=None):
    #     self.module = get_object_or_404(Module,
    #                                     id=module_id,
    #                                     course__owner=request.user)
    #     self.model = self.get_model(model_name)
    #     if id:
    #         self.obj = get_object_or_404(self.model,
    #                                      id=id,
    #                                      owner=request.user)
    #     return super().dispatch(request, module_id, model_name, id)

    def get(self, request,):
        form = FolderCreateForm()
        return self.render_to_response({'form': form})

    def post(self, request):
        logger.error(request.user)
        # user = User.get(username=request.user.id)
        currentuser = Member.objects.get(django_user_id=request.user.id)
        logger.error(str(currentuser.groups_manager_group_set))
        rootFolder = TreeItem.objects.get(id=1)

        # pdb.set_trace()

        form = FolderCreateForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.owner = request.user
            obj.save()
            # pdb.set_trace()
            TreeItem.objects.create(content_object=obj, parent=rootFolder)

            # pdb.set_trace()
        return redirect('manage_folder_list')
        # return self.render_to_response({'form': form,
        #                                 'object': self.obj})


class DocumentCreateUpdateView(TemplateResponseMixin, View):
    module = None
    model = None
    obj = None
    template_name = 'folders/manage/Document/form.html'
    # def get_model(self, model_name):
    #     if model_name in ['text', 'video', 'image', 'file']:
    #         return apps.get_model(app_label='courses',
    #                               model_name=model_name)
    #     return None
    # def get_form(self, model, *args, **kwargs):
    #     Form = modelform_factory(model, exclude=['owner',
    #                                              'order',
    #                                              'created',
    #                                              'updated'])
    #     return Form(*args, **kwargs)

    # def dispatch(self, request, module_id, model_name, id=None):
    #     self.module = get_object_or_404(Module,
    #                                     id=module_id,
    #                                     course__owner=request.user)
    #     self.model = self.get_model(model_name)
    #     if id:
    #         self.obj = get_object_or_404(self.model,
    #                                      id=id,
    #                                      owner=request.user)
    #     return super().dispatch(request, module_id, model_name, id)

    def get(self, request,  *args, **kwargs):
        form = DocumentCreateForm()
        return self.render_to_response({'form': form})

    def post(self, request, folder_id, id=None):


        # rootFolder = TreeItem.objects.get(id=folder_id)

        rootFolder = TreeItem.objects.get(id=1)

        cur = Member.objects.get(django_user_id=request.user.id)
        # group = Group.objects.get(name=rootFolder.content_object.name)
        group = Group.objects.get(id=1)
        pdb.set_trace()
        # lit.add_member(cur)
        custom_permissions = {
            # 'owner': ['view', 'change', 'delete'],
            'group': ['view', 'change'],
            'groups_upstream': [],
            'groups_downstream': [],
            'groups_siblings': [],
        }
        # pdb.set_trace()


        # pdb.set_trace()

        form = DocumentCreateForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.owner = request.user
            obj.folder = rootFolder.content_object
            obj.save()
            pdb.set_trace()
            newDoc = TreeItem.objects.create(content_object=obj, parent=rootFolder)
            cur.assign_object(group, newDoc, custom_permissions=custom_permissions)

            # pdb.set_trace()
        return redirect('manage_folder_list')



# class ContentCreateUpdateView(TemplateResponseMixin, View):
#     module = None
#     model = None
#     obj = None
#     template_name = 'courses/manage/content/form.html'
#
#     def get_model(self, model_name):
#         if model_name in ['text', 'video', 'image', 'file']:
#             return apps.get_model(app_label='courses',
#                                   model_name=model_name)
#         return None
#
#     def get_form(self, model, *args, **kwargs):
#         Form = modelform_factory(model, exclude=['owner',
#                                                  'order',
#                                                  'created',
#                                                  'updated'])
#         return Form(*args, **kwargs)
#
#     def dispatch(self, request, module_id, model_name, id=None):
#         self.module = get_object_or_404(Module,
#                                         id=module_id,
#                                         course__owner=request.user)
#         self.model = self.get_model(model_name)
#         if id:
#             self.obj = get_object_or_404(self.model,
#                                          id=id,
#                                          owner=request.user)
#         return super().dispatch(request, module_id, model_name, id)
#
#     def get(self, request, module_id, model_name, id=None):
#         form = self.get_form(self.model, instance=self.obj)
#         return self.render_to_response({'form': form,
#                                         'object': self.obj})
#
#     def post(self, request, module_id, model_name, id=None):
#         form = self.get_form(self.model,
#                              instance=self.obj,
#                              data=request.POST,
#                              files=request.FILES)
#
#         if form.is_valid():
#             obj = form.save(commit=False)
#             obj.owner = request.user
#             obj.save()
#             if not id:
#                 # new content
#                 Content.objects.create(module=self.module,
#                                        item=obj)
#             return redirect('module_content_list', self.module.id)
#         return self.render_to_response({'form': form,
#                                         'object': self.obj})
