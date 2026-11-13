"""Synthetic fixtures only: these are not experiment results."""
import tempfile
import unittest
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from geometry import colmap_pose,write_tum,read_tum,match_times,align,trajectory_metrics,triangulate,rotate_intrinsics,resize_intrinsics,encode_depth
from reference import parse_images
from media import nearest_frames
from common import Stage,ROOT,atomic

class GeometryTests(unittest.TestCase):
    def test_colmap_inverse(self):
        r=Rotation.from_euler('xyz',[20,30,40],degrees=True); c=np.array([2.,-1.,4.]); q=r.as_quat()
        twc=colmap_pose(q[[3,0,1,2]],-r.as_matrix()@c)
        np.testing.assert_allclose(twc[:3,3],c,atol=1e-10)
        np.testing.assert_allclose(twc[:3,:3],r.as_matrix().T,atol=1e-10)

    def test_colmap_alternating_blank_and_spaces(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'images.txt'; p.write_text('# header\n1 1 0 0 0 0 0 0 1 image with spaces.png\n\n2 1 0 0 0 -1 0 0 1 other.png\n1 2 3\n')
            x=parse_images(p); self.assertEqual(len(x),2); self.assertIn('image with spaces.png',x)
            np.testing.assert_allclose(x['other.png']['Twc'][0][3],1)

    def test_tum_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            poses=np.repeat(np.eye(4)[None],3,axis=0); poses[:,0,3]=[0,1,2]
            p=Path(d)/'a.tum'; write_tum(p,[.1,.2,.3],poses)
            data=read_tum(p); np.testing.assert_allclose(data[:,1],[0,1,2]); self.assertEqual(data.shape,(3,8))

    def test_matching_unique(self):
        p=match_times([0,.01,.1],[.005,.1],.02)
        self.assertEqual(len(p),2); self.assertEqual(len(set(p[:,1])),2)

    def test_align_and_ate(self):
        rng=np.random.default_rng(1); x=rng.normal(size=(30,3)); r=Rotation.from_euler('xyz',[.1,.3,.4]).as_matrix(); y=2.5*(r@x.T).T+[3,4,5]
        k,_,_=align(x,y,True); self.assertAlmostEqual(k,2.5)
        t=np.arange(30)*.1; q=np.tile([0,0,0,1.],(30,1)); e=np.c_[t,x,q]; g=np.c_[t,y,q]
        m,_,_=trajectory_metrics(e,g)
        self.assertLess(m['ate_scaled_m'],1e-10); self.assertGreater(m['ate_unscaled_m'],.1)
        g[:,1:4]=(r@x.T).T+[3,4,5]
        m,_,_=trajectory_metrics(e,g); self.assertLess(m['ate_unscaled_m'],1e-10)

    def test_rpe_gaps(self):
        t=np.r_[np.arange(0,.5,.1),np.arange(2,2.5,.1)]
        xyz=np.c_[np.sin(t),np.cos(t),t]; q=np.tile([0,0,0,1.],(len(t),1)); d=np.c_[t,xyz,q]
        m,_,_=trajectory_metrics(d,d,interval=1,pair_tolerance=.2,max_gap=.25)
        self.assertEqual(m['rpe_pairs'],0); self.assertIsNone(m['rpe_rmse_m'])
        m,_,pairs=trajectory_metrics(d,d,interval=.2,pair_tolerance=.01,max_gap=.25)
        self.assertGreater(len(pairs),0); self.assertAlmostEqual(m['rpe_rmse_m'],0)

    def test_triangulation_and_degeneracy(self):
        k=np.array([[500,0,320],[0,500,240],[0,0,1.]])
        poses=np.repeat(np.eye(4)[None],4,axis=0); poses[:,0,3]=[-1,-.3,.3,1]
        recovered=[]
        for x in [np.array([0.,0.,4.]),np.array([.5,0.,4.])]:
            pc=x-poses[:,:3,3]; uv=(k@pc.T).T; uv=uv[:,:2]/uv[:,2:]
            p,_=triangulate(uv,poses,k); recovered.append(p)
            np.testing.assert_allclose(p,x,atol=1e-9)
        self.assertAlmostEqual(np.linalg.norm(recovered[1]-recovered[0]),.5)
        poses[:,0,3]=0
        with self.assertRaises(ValueError): triangulate(np.tile([320,240],(4,1)),poses,k)

    def test_intrinsic_rotation(self):
        k=np.array([[500,0,300],[0,600,200],[0,0,1.]])
        kr,size=rotate_intrinsics(k,640,480,90)
        self.assertEqual(size,(480,640)); self.assertEqual(kr[0,2],279); self.assertEqual(kr[1,2],300)
        original,_=rotate_intrinsics(kr,*size,270); np.testing.assert_allclose(original,k)

    def test_marker_outliers_and_annotation_order(self):
        rng=np.random.default_rng(14); k=np.array([[500.,0,320],[0,500,240],[0,0,1.]])
        poses=np.repeat(np.eye(4)[None],25,axis=0); poses[:,0,3]=np.linspace(-1,1,25)
        point=np.array([.2,.1,4.]); pc=point-poses[:,:3,3]; uv=(k@pc.T).T; uv=uv[:,:2]/uv[:,2:]
        uv[:7]+=rng.uniform(50,150,(7,2)); uv[7:]+=rng.normal(0,.1,(18,2))
        fitted,diag=triangulate(uv,poses,k)
        np.testing.assert_allclose(fitted,point,atol=.01)
        self.assertFalse(any(diag['inliers'][:7])); self.assertEqual(sum(diag['inliers']),18)
        permutation=rng.permutation(25); fitted2,diag2=triangulate(uv[permutation],poses[permutation],k)
        np.testing.assert_allclose(fitted2,fitted,atol=1e-9)
        np.testing.assert_array_equal(np.array(diag2['inliers'])[np.argsort(permutation)],diag['inliers'])

    def test_factor_once(self):
        d=np.array([[1.,2.,np.nan,20.]])
        raw,m=encode_depth(d,5000)
        self.assertEqual(int(raw[0,1]),10000); self.assertEqual(m['clipped_pixels'],1)
        np.testing.assert_allclose(raw[0,:2]/5000,d[0,:2])

    def test_resize_preserves_projected_pixel_centres(self):
        k=np.array([[500.,0,300],[0,600,200],[0,0,1.]])
        xyz=np.array([.4,-.2,3.]); old=k@xyz; old=old[:2]/old[2]
        newk=resize_intrinsics(k,(640,480),(320,240)); uv=newk@xyz; uv=uv[:2]/uv[2]
        np.testing.assert_allclose(uv,(old+.5)*.5-.5)

    def test_vfr_nearest_no_duplicate(self):
        t=[0,.031,.067,.103,.14]; x=nearest_frames(t,10)
        self.assertEqual(list(x),[0,3]); self.assertEqual(len(x),len(set(x)))

    def test_stage_resume_invalidation(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'part4') as d:
            work=Path(d); source=work/'input'; source.write_text('source')
            stage=Stage(work,'unit_fixture',{'a':1},[source]); stage.begin(); atomic(stage.path/'out','test'); stage.finish(['out'])
            self.assertTrue(Stage(work,'unit_fixture',{'a':1},[source]).cached())
            self.assertFalse(Stage(work,'unit_fixture',{'a':2},[source]).cached())
            atomic(stage.path/'out','corrupt'); self.assertFalse(stage.cached())

if __name__=='__main__': unittest.main()
