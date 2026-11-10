"""
Uji Kelola Akses Role (Backlog #4, FR-AUT).
"""
import pytest
from django.http import HttpResponse
from django.urls import reverse

from accounts.decorators import role_required, _get_acting_role
from accounts.models import User


@pytest.fixture
def users_setup(db):
    re_user = User.objects.create_user(
        username='re_admin',
        email='re@katawarga.local',
        password='password123',
        role=User.RolePengguna.REQUIREMENTS_ENGINEER,
    )
    dev_user = User.objects.create_user(
        username='dev_coder',
        email='dev@katawarga.local',
        password='password123',
        role=User.RolePengguna.TIM_DEVELOPER,
    )
    po_user = User.objects.create_user(
        username='po_lead',
        email='po@katawarga.local',
        password='password123',
        role=User.RolePengguna.PRODUCT_OWNER,
    )
    return {
        're': re_user,
        'dev': dev_user,
        'po': po_user,
    }


@pytest.mark.django_db
def test_kelola_role_view_access(client, users_setup):
    re_user = users_setup['re']
    dev_user = users_setup['dev']

    # RE bisa akses halaman kelola role
    client.force_login(re_user)
    resp = client.get(reverse('accounts:kelola_role'))
    assert resp.status_code == 200
    assert 'Kelola Akses Role Pengguna' in resp.content.decode('utf-8')

    # Developer tidak berwenang mengelola role
    client.force_login(dev_user)
    resp_dev = client.get(reverse('accounts:kelola_role'))
    assert resp_dev.status_code == 403


@pytest.mark.django_db
def test_ubah_role_sukses(client, users_setup):
    re_user = users_setup['re']
    dev_user = users_setup['dev']

    client.force_login(re_user)
    url = reverse('accounts:ubah_role', kwargs={'pk': dev_user.pk})
    resp = client.post(url, {'role': User.RolePengguna.ANALYST}, follow=True)

    assert resp.status_code == 200
    dev_user.refresh_from_db()
    assert dev_user.role == User.RolePengguna.ANALYST


@pytest.mark.django_db
def test_ubah_role_invalid(client, users_setup):
    re_user = users_setup['re']
    dev_user = users_setup['dev']

    client.force_login(re_user)
    url = reverse('accounts:ubah_role', kwargs={'pk': dev_user.pk})
    resp = client.post(url, {'role': 'INVALID_ROLE'}, follow=True)

    dev_user.refresh_from_db()
    assert dev_user.role == User.RolePengguna.TIM_DEVELOPER  # Tidak berubah



@pytest.mark.django_db
def test_switch_acting_role(client, users_setup, settings):
    settings.DEBUG = True
    user = users_setup["re"]
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    client.force_login(user)
    url = reverse("accounts:switch_role")
    response = client.post(
        url,
        {
            "acting_role": User.RolePengguna.PRODUCT_OWNER,
        },
    )
    assert response.status_code == 302
    assert (
        client.session.get("acting_role")
        == User.RolePengguna.PRODUCT_OWNER
    )
    response = client.post(
        url,
        {
            "acting_role": User.RolePengguna.TIM_DEVELOPER,
        },
    )
    assert response.status_code == 302

    assert (
        client.session.get("acting_role")
        == User.RolePengguna.TIM_DEVELOPER
    )
    response = client.post(
        url,
        {
            "acting_role": "",
        },
    )
    assert response.status_code == 302
    assert client.session.get("acting_role") is None


@pytest.mark.django_db
def test_role_required_decorator(rf, users_setup):
    @role_required(User.RolePengguna.REQUIREMENTS_ENGINEER)
    def dummy_view(request):
        return HttpResponse('OK')

    # RE sukses
    req_re = rf.get('/')
    req_re.user = users_setup['re']
    assert dummy_view(req_re).status_code == 200

    # PO gagal (403)
    req_po = rf.get('/')
    req_po.user = users_setup['po']
    assert dummy_view(req_po).status_code == 403

