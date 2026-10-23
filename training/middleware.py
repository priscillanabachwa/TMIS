from django.contrib.auth import logout
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from .models import PortalIdentity,Trainee,Staff

class StaffOnlyMiddleware:
    """Retains its original settings path while adding scoped portal access."""
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        request.portal_role=None
        request.portal_profile=None
        if request.user.is_authenticated and not request.user.is_superuser:
            identity=PortalIdentity.objects.select_related('Account').filter(Login_id=request.user.pk).first() if request.user.pk else None
            if request.user.is_staff and identity is None:
                return self.get_response(request)
            if identity is None:
                return HttpResponseForbidden('No training portal is linked to this sign-in. Ask the website administrator for access.')
            account=identity.Account
            profile=None
            if account.Role=='trainee': profile=Trainee.objects.filter(User_id=account.pk,TraineeStatus='active').first()
            elif account.Role=='trainer': profile=Staff.objects.filter(User_id=account.pk,Role='trainer',StaffStatus='active').first()
            if account.AccountStatus!='active' or profile is None:
                logout(request)
                return HttpResponseForbidden('This project account or profile is inactive. Contact the administrator.')
            request.portal_identity=identity
            request.portal_role=account.Role
            request.portal_profile=profile
            if request.path_info=='/': return redirect('portal_home')
            if not (request.path_info.startswith('/portal/') or request.path_info in ['/login/','/logout/']):
                return HttpResponseForbidden('This page is restricted to training administrators and operators.')
        return self.get_response(request)
