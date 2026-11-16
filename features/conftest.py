"""
conftest.py untuk BDD tests di folder features/.
Menyediakan fixtures shared yang digunakan oleh semua step definitions.
"""
import pytest
from django.test import Client
from django.utils import timezone


@pytest.fixture(autouse=True)
def enable_db_access_for_all_bdd_tests(db):
    """Memastikan test database selalu siap untuk semua skenario BDD."""
    pass


@pytest.fixture
def client():
    """Django test client."""
    return Client()


@pytest.fixture
def re_user(db):
    """Pengguna Requirements Engineer."""
    from accounts.models import User
    user, _ = User.objects.get_or_create(
        username='bdd_re_user',
        defaults={
            'role': User.RolePengguna.REQUIREMENTS_ENGINEER,
            'email': 're@katawarga.test',
        }
    )
    user.set_password('testpass123')
    user.save()
    return user


@pytest.fixture
def analyst_user(db):
    """Pengguna Analyst."""
    from accounts.models import User
    user, _ = User.objects.get_or_create(
        username='bdd_analyst_user',
        defaults={
            'role': User.RolePengguna.ANALYST,
            'email': 'analyst@katawarga.test',
        }
    )
    user.set_password('testpass123')
    user.save()
    return user


@pytest.fixture
def po_user(db):
    """Pengguna Product Owner."""
    from accounts.models import User
    user, _ = User.objects.get_or_create(
        username='bdd_po_user',
        defaults={
            'role': User.RolePengguna.PRODUCT_OWNER,
            'email': 'po@katawarga.test',
        }
    )
    user.set_password('testpass123')
    user.save()
    return user


@pytest.fixture
def dev_user(db):
    """Pengguna Tim Developer."""
    from accounts.models import User
    user, _ = User.objects.get_or_create(
        username='bdd_dev_user',
        defaults={
            'role': User.RolePengguna.TIM_DEVELOPER,
            'email': 'dev@katawarga.test',
        }
    )
    user.set_password('testpass123')
    user.save()
    return user


@pytest.fixture
def aplikasi(db):
    """Objek Aplikasi dummy untuk testing."""
    from reviews.models import Aplikasi
    app, _ = Aplikasi.objects.get_or_create(
        package_name='com.test.app',
        defaults={
            'nama_aplikasi': 'SATU SEHAT',
            'kategori': 'Kesehatan',
            'aktif': True,
        }
    )
    return app


@pytest.fixture
def ulasan_factory(db, aplikasi):
    """Factory untuk membuat Ulasan."""
    from reviews.models import Ulasan
    _counter = [0]

    def _create(teks='Ulasan uji coba', status=Ulasan.StatusFilter.LOLOS, skor_bintang=1):
        _counter[0] += 1
        return Ulasan.objects.create(
            aplikasi=aplikasi,
            review_id=f'bdd_review_{_counter[0]}_{timezone.now().timestamp()}',
            isi_ulasan=teks,
            skor_bintang=skor_bintang,
            tanggal_ulasan=timezone.now().date(),
            status_filter=status,
        )
    return _create


@pytest.fixture
def hasil_ekstraksi_factory(db, ulasan_factory):
    """Factory untuk membuat HasilEkstraksi."""
    from extraction.models import HasilEkstraksi

    def _create(teks_who='pengguna', teks_what='gagal login', teks_why='',
                status=HasilEkstraksi.StatusValidasi.MENUNGGU_VALIDASI, ulasan=None):
        if ulasan is None:
            ulasan = ulasan_factory()
        return HasilEkstraksi.objects.create(
            ulasan=ulasan,
            teks_who=teks_who,
            teks_what=teks_what,
            teks_why=teks_why,
            skor_confidence=0.75,
            status_validasi=status,
        )
    return _create


@pytest.fixture
def cluster_factory(db):
    """Factory untuk membuat Cluster."""
    from extraction.models import Cluster

    def _create(nama='Cluster Uji', jumlah=5, status=Cluster.StatusCluster.MENUNGGU_VALIDASI):
        return Cluster.objects.create(
            nama_topik=nama,
            jumlah_anggota=jumlah,
            skor_signifikansi=float(jumlah) * 1.0,
            status_cluster=status,
        )
    return _create


@pytest.fixture
def user_story_factory(db, cluster_factory):
    """Factory untuk membuat UserStory."""
    from extraction.models import Cluster
    from stories.models import UserStory

    def _create(cluster=None, prioritas=UserStory.LevelPrioritas.TINGGI,
                status=UserStory.StatusPersetujuan.MENUNGGU_PERSETUJUAN,
                kebutuhan='memperbaiki fitur login'):
        if cluster is None:
            cluster = cluster_factory(status=Cluster.StatusCluster.TERVALIDASI)
        return UserStory.objects.create(
            cluster=cluster,
            peran='pengguna',
            kebutuhan=kebutuhan,
            alasan='agar aplikasi dapat digunakan',
            skor_prioritas=100.0,
            kategori_prioritas=prioritas,
            status_persetujuan=status,
        )
    return _create


@pytest.fixture
def backlog_item_factory(db, user_story_factory):
    """Factory untuk membuat BacklogItem."""
    from backlog.models import BacklogItem
    from stories.models import UserStory

    def _create(user_story=None, status=BacklogItem.StatusEksekusi.SIAP_DIEKSEKUSI):
        if user_story is None:
            user_story = user_story_factory(status=UserStory.StatusPersetujuan.DISETUJUI)
        return BacklogItem.objects.create(
            user_story=user_story,
            status_eksekusi=status,
        )
    return _create
