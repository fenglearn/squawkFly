#!/usr/local/bin/python

import sys
import cv2
import cv2.cv as cv
import numpy as np
import math
import matplotlib.pyplot as plt
from collections import namedtuple
from mpl_toolkits.mplot3d import Axes3D

import triangulation as tri
import structureTools as struc
import plotting as plot

np.set_printoptions(suppress=True)
plt.style.use('ggplot')

Point = namedtuple("Point", "x y")

# Calibration matrices:
K1 = np.mat(struc.CalibArray(5, 5, 5))
K2 = np.mat(struc.CalibArray(5, 5, 5))


# simulated projection data with project.py
def getSimulationData(folder):
    path = 'simulation_data/' + str(folder) + '/'
    pts1 = []
    pts2 = []
    original_3Ddata = []

    with open(path + 'pts1.txt') as datafile:
        data = datafile.read()
        datafile.close()

    data = data.split('\n')
    for row in data:
        x = float(row.split()[0])
        y = float(row.split()[1])
        pts1.append([x, y])

    with open(path + 'pts2.txt') as datafile:
        data = datafile.read()
        datafile.close()

    data = data.split('\n')
    for row in data:
        x = float(row.split()[0])
        y = float(row.split()[1])
        pts2.append([x, y])

    with open(path + '3d.txt') as datafile:
        data = datafile.read()
        datafile.close()

    data = data.split('\n')
    for row in data:
        x = float(row.split()[0])
        y = float(row.split()[1])
        z = float(row.split()[1])
        original_3Ddata.append([x, y, z])

    return original_3Ddata, pts1, pts2


try:
    sim = sys.argv[1]
except IndexError:
    sim = 1

original_3Ddata, pts1_raw, pts2_raw = getSimulationData(sim)

# Image coords: (x, y)
pts1 = np.array(pts1_raw, dtype='float32')
pts2 = np.array(pts2_raw, dtype='float32')

# Normalised homogenous image coords: (x, y, 1)
norm_pts1 = struc.normalise_homogenise(pts1, K1)
norm_pts2 = struc.normalise_homogenise(pts2, K2)

# Inhomogenous but normalised K_inv(x, y) (for if you want to calc E directly)
inhomog_norm_pts1 = np.delete(norm_pts1, 2, 1)
inhomog_norm_pts2 = np.delete(norm_pts2, 2, 1)

# Arrays FOR Rt computation
W, W_inv = struc.initWarrays()  # HZ 9.13


def run():
    plot.plot3D(original_3Ddata, 'Original 3D Data')
    plot.plot2D(pts1_raw, 'First image')
    plot.plot2D(pts2_raw, 'Second image')

    # FUNDAMENTAL MATRIX
    F = getFundamentalMatrix(pts1, pts2)

    # ESSENTIAL MATRIX (HZ 9.12)
    E, w, u, vt = getEssentialMatrix(F, K1, K2)

    # CONSTRAINED ESSENTIAL MATRIX
    E_prime, w2, u2, vt2 = getConstrainedEssentialMatrix(u, vt)

    # scale = E[0, 0] / E_prime[0, 0]
    # E_prime = E_prime * scale
    # print "\n> scaled:\n", E_prime

    # PROJECTION/CAMERA MATRICES from E (or E_prime?) (HZ 9.6.2)
    P1, P2 = getNormalisedPMatrices(u, vt)
    P1_mat = np.mat(P1)
    P2_mat = np.mat(P2)

    # FULL PROJECTION MATRICES (with K) P = K[Rt]
    KP1 = K1 * P1_mat
    KP2 = K2 * P2_mat

    print "\n> KP1:\n", KP1
    print "\n> KP2:\n", KP2

    # TRIANGULATION
    p3d_ls = triangulateLS(KP1, KP2, pts1, pts2)

    # alternative triangulation
    points3dcv = triangulateCV(KP1, KP2, pts1, pts2)
    points3dcv = cv2.convertPointsFromHomogeneous(points3dcv)
    p3d_cv = points3dcv.tolist()
    p3d_cv = fixExtraneousParentheses(p3d_cv)

    # PLOTTING
    plot.plot3D(p3d_cv, '3D Reconstruction (Scale ambiguity)')
    reprojectionError(K1, P1_mat, K2, P2_mat, p3d_ls)


# get the Fundamental matrix by the normalised eight point algorithm
def getFundamentalMatrix(pts1, pts2):

    # 8point normalisation
    pts1_, T1 = eightPointNormalisation(pts1)
    pts2_, T2 = eightPointNormalisation(pts2)

    plot.plot2D(pts1, pts1_, '8pt Normalisation on Image 1')
    plot.plot2D(pts2, pts2_, '8pt Normalisation on Image 2')

    # normalised 8-point algorithm
    F_, mask = cv2.findFundamentalMat(pts1_, pts2_, cv.CV_FM_8POINT)
    is_singular(F_)

    # denormalise
    F = T2.T * np.mat(F_) * T1

    # test on original coordinates
    print "\n> Fundamental:\n", F
    testFundamentalReln(F, pts1, pts2)
    return F


# translate and scale image points, return both points and the transformation T
def eightPointNormalisation(pts):
    print "> 8POINT NORMALISATION"

    cx = 0
    cy = 0
    pts_ = []

    for p in pts:
        cx += p[0]
        cy += p[1]

    cx = cx / len(pts)
    cy = cy / len(pts)

    # translation to (cx,cy) = (0,0)
    T = np.mat([[1, 0, -cx],
                [0, 1, -cy],
                [0, 0, 1]])

    print "Translate by:", -cx, -cy

    # now scale to rms_d = sqrt(2)
    total_d = 0
    for p in pts:
        d = math.hypot(p[0] - cx, p[1] - cy)
        total_d += (d * d)

    # square root of the mean of the squares
    rms_d = math.sqrt((total_d / len(pts)))

    scale_factor = math.sqrt(2) / rms_d
    print "Scale by:", scale_factor

    T = scale_factor * T
    T[2, 2] = 1
    print "T:\n", T

    # apply the transformation
    hom = cv2.convertPointsToHomogeneous(pts)
    for h in hom:
        h_ = T * h.T
        pts_.append(h_)

    pts_ = cv2.convertPointsFromHomogeneous(np.array(pts_, dtype='float32'))
    check8PointNormalisation(pts_)

    # make sure the normalised points are in the same format as original
    pts_r = []
    for p in pts_:
        pts_r.append(p[0])
    pts_r = np.array(pts_r, dtype='float32')

    return pts_r, T


def check8PointNormalisation(pts_):
    # average distance from origin should be sqrt(2) and centroid = origin
    d_tot = 0
    cx = 0
    cy = 0
    for p in pts_:
        cx += p[0][0]
        cx += p[0][1]
        d = math.hypot(p[0][0], p[0][1])
        d_tot += d

    avg = d_tot / len(pts_)
    cx = cx / len(pts_)
    cy = cy / len(pts_)

    assert(avg - math.sqrt(2) < 0.01), "Scale factor is wrong"
    assert(cx < 0.1 and cy < 0.1), "Centroid not at origin"


def getEssentialMatrix(F, K1, K2):
    E = K2.T * np.mat(F) * K1
    print "\n> Essential:\n", E
    testEssentialReln(E, norm_pts1, norm_pts2)

    w, u, vt = cv2.SVDecomp(E)
    print "u:\n", u
    print "vt:\n", vt
    print "\n> Singular values:\n", w
    return E, w, u, vt


# https://en.wikipedia.org/wiki/Eight-point_algorithm#Step_3:_Enforcing_the_internal_constraint
def getConstrainedEssentialMatrix(u, vt):
    diag = np.mat(np.diag([1, 1, 0]))

    E_prime = np.mat(u) * diag * np.mat(vt)
    print "\n> Constrained Essential = u * diag(1,1,0) * vt:\n", E_prime
    testEssentialReln(E_prime, norm_pts1, norm_pts2)

    w2, u2, vt2 = cv2.SVDecomp(E_prime)
    print "\n> Singular values:\n", w2

    return E_prime, w2, u2, vt2


def getNormalisedPMatrices(u, vt):
    R1 = np.mat(u) * np.mat(W) * np.mat(vt)
    R2 = np.mat(u) * np.mat(W.T) * np.mat(vt)
    t1 = u[:, 2]
    t2 = -1 * u[:, 2]

    R, t = getValidRtCombo(R1, R2, t1, t2)

    # NORMALISED CAMERA MATRICES P = [Rt]
    P1 = BoringCameraArray()  # I|0
    P2 = CameraArray(R, t)    # R|t

    print "\n> P1:\n", P1
    print "\n> P2:\n", P2

    return P1, P2


def getValidRtCombo(R1, R2, t1, t2):
    # enforce positive depth combination of Rt using normalised coords
    if testRtCombo(R1, t1, norm_pts1, norm_pts2):
        print "\n> RT: R1 t1"
        R = R1
        t = t1

    elif testRtCombo(R1, t2, norm_pts1, norm_pts2):
        print "\n> RT: R1 t2"
        R = R1
        t = t2

    elif testRtCombo(R2, t1, norm_pts1, norm_pts2):
        print "\n> RT: R2 t1"
        R = R2
        t = t1

    elif testRtCombo(R2, t2, norm_pts1, norm_pts2):
        print "\n> RT: R2 t2"
        R = R2
        t = t2

    else:
        print "ERROR: No positive depth Rt combination"
        sys.exit()

    print "R:\n", R
    print "t:\n", t
    return R, t


def testFundamentalReln(F, pts1, pts2):
    # check that xFx = 0 for homog coords x x'
    F = np.mat(F)
    is_singular(F)

    pts1_hom = cv2.convertPointsToHomogeneous(pts1)
    pts2_hom = cv2.convertPointsToHomogeneous(pts2)

    errors = []
    sum_err = 0

    # forwards
    for i in range(0, len(pts1_hom)):
        this_err = abs(np.mat(pts1_hom[i]) * F * np.mat(pts2_hom[i]).T)
        sum_err += this_err[0, 0]
        errors.append(this_err[0, 0])

    # backwards
    for i in range(0, len(pts2_hom)):
        this_err = abs(np.mat(pts2_hom[i]) * F * np.mat(pts1_hom[i]).T)
        sum_err += this_err[0, 0]
        errors.append(this_err[0, 0])

    err = sum_err / (2 * len(pts1_hom))
    print "> x'Fx = 0:", err

    # inspec the error distribution
    plot.plotOrderedBar(errors,
                        name='x\'Fx = 0 Test Results ',
                        ylabel='Deflection from zero',
                        xlabel='Point Index')

    # test the epilines
    pts1_epi = pts1.reshape(-1, 1, 2)
    pts2_epi = pts2.reshape(-1, 1, 2)

    # lines computed from pts1
    lines1 = cv2.computeCorrespondEpilines(pts1_epi, 1, F)
    lines1 = lines1.reshape(-1, 3)

    # lines computed frmo pts2
    lines2 = cv2.computeCorrespondEpilines(pts2_epi, 2, F)
    lines2 = lines2.reshape(-1, 3)

    distances2 = []
    for l, p in zip(lines1, pts2):
        distances2.append(distanceToEpiline(l, p))

    distances1 = []
    for l, p in zip(lines2, pts1):
        distances1.append(distanceToEpiline(l, p))

    plot.plotOrderedBar(distances1,
                        'Image 1: Point-Epiline Distances', 'Index', 'px')

    plot.plotOrderedBar(distances2,
                        'Image 2: Point-Epiline Distances', 'Index', 'px')

    # overlay lines2 on pts1
    plot.plotEpilines(lines2, pts1, 1)

    # overlay lines1 on pts2
    plot.plotEpilines(lines1, pts2, 2)


def is_singular(a):
    det = np.linalg.det(a)
    s = not is_invertible(a)
    print "> Singular:", s
    assert(s is True), "Singularity problems."


def is_invertible(a):
    return a.shape[0] == a.shape[1] and np.linalg.matrix_rank(a) == a.shape[0]


def testEssentialReln(E, nh_pts1, nh_pts2):
    # check that x'Ex = 0 for normalised, homog coords x x'
    E = np.mat(E)
    is_singular(E)

    err = 0
    for i in range(0, len(nh_pts1)):
        err += abs(np.mat(nh_pts1[i]) * E * np.mat(nh_pts2[i]).T)

    err = err[0, 0] / len(nh_pts1)
    print "> x'Ex = 0:", err


# linear least squares triangulation for one 3-space point X
def triangulateLS(P1, P2, pts1, pts2):
    points3d = []

    for i in range(0, len(pts1)):

        x1 = pts1[i][0]
        y1 = pts1[i][1]

        x2 = pts2[i][0]
        y2 = pts2[i][1]

        p1 = Point(x1, y1)
        p2 = Point(x2, y2)

        X = tri.LinearTriangulation(P1, p1, P2, p2)

        points3d.append(X[1])

    return points3d


# expects normalised points
def triangulateCV(KP1, KP2, pts1, pts2):
    points4d = cv2.triangulatePoints(KP1, KP2, pts1.T, pts2.T)
    points4d = points4d.T
    print "\n> cv2.triangulatePoints:\n"
    for point in points4d:
        k = 1 / point[3]
        point = point * k

    return points4d


def testRtCombo(R, t, pts1, pts2):
    P1 = BoringCameraArray()
    P2 = CameraArray(R, t)
    points3d = []

    for i in range(0, len(pts1)):
        x1 = pts1[i][0]
        y1 = pts1[i][0]
        x2 = pts2[i][0]
        y2 = pts2[i][0]

        u1 = Point(x1, y1)
        u2 = Point(x2, y2)

        X = tri.LinearTriangulation(P1, u1, P2, u2)
        points3d.append(X[1])

    for point in points3d:
        if point[2] < 0:
            return False

    return True


# used for checking the triangulation - provide UNNORMALISED DATA
def reprojectionError(K1, P1_mat, K2, P2_mat, points3d):

    # Nx4 array for filling with homogeneous points
    new = np.zeros((len(points3d), 4))

    for i, point in enumerate(points3d):
        new[i][0] = point[0]
        new[i][1] = point[1]
        new[i][2] = point[2]
        new[i][3] = 1

    errors1 = []
    errors2 = []
    reprojected1 = []
    reprojected2 = []

    # for each 3d point
    for i, X in enumerate(new):
        # x_2d = K * P * X_3d
        xp1 = K1 * P1_mat * np.mat(X).T
        xp2 = K2 * P2_mat * np.mat(X).T

        # normalise the projected (homogenous) coordinates
        # (x,y,1) = (xz,yz,z) / z
        xp1 = xp1 / xp1[2]
        xp2 = xp2 / xp2[2]

        reprojected1.append(xp1)
        reprojected2.append(xp2)

        # and get the orginally measured points
        x1 = pts1[i]
        x2 = pts2[i]

        # difference between them is:
        dist1 = math.hypot(xp1[0] - x1[0], xp1[1] - x1[1])
        dist2 = math.hypot(xp2[0] - x2[0], xp2[1] - x2[1])
        errors1.append(dist1)
        errors2.append(dist2)

    avg1 = sum(errors1) / len(errors1)
    avg2 = sum(errors2) / len(errors2)
    print "\n> average reprojection error in image 1:", avg1
    print "\n> average reprojection error in image 2:", avg2

    plot.plotOrderedBar(errors1, 'Reprojection Error Image 1', 'Index', 'px')
    plot.plotOrderedBar(errors2, 'Reprojection Error Image 2', 'Index', 'px')

    plot.plot2D(reprojected1, pts1,
                'Reprojection of Reconstruction onto Image 1')
    plot.plot2D(reprojected2, pts2,
                'Reprojection of Reconstruction onto Image 2')


# find the distance between an epiline and image point pair
def distanceToEpiline(line, pt):

    # ax + by + c = 0
    a, b, c = line[0], line[1], line[2]

    # image point coords
    x = pt[0]
    y = pt[1]

    # y = mx + k (epiline)
    m1 = -a / b
    k1 = -c / b

    # y = -1/m x + k2 (perpedicular line through p)
    m2 = -1 / m1
    k2 = y - (m2 * x)

    # x at point of intersection:
    x_inter = (k2 - k1) / (m1 - m2)

    # y1(x) and y2(x) should be the same
    y_inter1 = (m1 * x) + k1
    y_inter2 = (m2 * x) + k2
    message = "Intersection point is wrong " + \
        str(y_inter1) + ' ' + str(y_inter2)

    assert(abs(y_inter1 - y_inter2) < 4), message

    # distance between p(x, y) and intersect(x, y)
    d = math.hypot(x - x_inter, y - y_inter1)

    return d


def fixExtraneousParentheses(points):
    temp = []
    for p in points:
        p = p[0]
        temp.append(p)

    new = temp
    return new


def BoringCameraArray():
    P = np.zeros((3, 4), dtype='float32')
    P[0][0] = 1
    P[1][1] = 1
    P[2][2] = 1
    return P


# P = [R|t]
def CameraArray(R, t):
    # just tack t on as a column to the end of R
    P = np.zeros((3, 4), dtype='float32')
    P[0][0] = R[0, 0]
    P[0][1] = R[0, 1]
    P[0][2] = R[0, 2]
    P[0][3] = t[0]

    P[1][0] = R[1, 0]
    P[1][1] = R[1, 1]
    P[1][2] = R[1, 2]
    P[1][3] = t[1]

    P[2][0] = R[2, 0]
    P[2][1] = R[2, 1]
    P[2][2] = R[2, 2]
    P[2][3] = t[2]

    return P

print "---------------------------------------------"
run()
