import numpy as np
import scipy.fftpack

def lowpass_filter(r,th):
    if np.pi/4. < r < np.pi/2.:
        return np.cos(np.pi/2.*np.log2(4.*r/np.pi))
    elif r <= np.pi/4.:
        return 1.
    else:
        return 0.

def highpass_filter(r,th):
    if np.pi/4. < r < np.pi/2.:
        return np.cos(np.pi/2.*np.log2(2.*r/np.pi))
    elif r <= np.pi/4.:
        return 0.
    else:
        return 1.

def angular_filter(r,th,k,K):
    c = np.math.factorial(K-1)/np.sqrt(K*np.math.factorial(2.*(K-1)))
    angle = np.min((np.abs(th-np.pi*k/K),2.*np.pi-np.abs(th-np.pi*k/K)))
    if angle < np.pi/2.:
        return c*np.power(2*np.cos(angle),K-1)
    else:
        return 0.

def bandpass_filter(r,th,n,N):
    return highpass_filter(r/np.power(2.,(N-n-1)/N),th) * lowpass_filter(r/np.power(2.,(N-n)/N),th)

def pyramid_filter(r,th,n,N,k,K):
    return bandpass_filter(r,th,n,N) * angular_filter(r,th,k,K)

def apply_filter(I,F,stretch=False):
    width = np.max(I.shape)
    d_y = 1/(2.*np.pi) if stretch else 1/(2.*np.pi*I.shape[0]/width)
    d_x = 1/(2.*np.pi) if stretch else 1/(2.*np.pi*I.shape[1]/width)
    w_y = scipy.fftpack.fftfreq(I.shape[0],d=d_y)
    w_x = scipy.fftpack.fftfreq(I.shape[1],d=d_x)
    W = np.stack((np.repeat(w_y.reshape(-1,1), I.shape[1], axis=1),np.repeat(w_x.reshape(1,-1), I.shape[0], axis=0)))
    R = np.linalg.norm(W,axis=0) 
    Th = np.arctan2(W[0],W[1])

    return I * np.vectorize(F)(R,Th)

def downsample2(I,method='crop'):
    if method == 'crop':
        window_left = lambda width_big, width_small: np.where(scipy.fftpack.fftshift(scipy.fftpack.fftfreq(width_big)) == 0)[0].flatten()[0] - np.where(scipy.fftpack.fftshift(scipy.fftpack.fftfreq(width_small)) == 0)[0].flatten()[0]
        new_h = int(np.ceil(I.shape[0]/2.))
        new_w = int(np.ceil(I.shape[1]/2.))
        offset_y = window_left(I.shape[0],new_h)
        offset_x = window_left(I.shape[1],new_w)
        return scipy.fftpack.ifftshift(scipy.fftpack.fftshift(I)[offset_y:offset_y+new_h,offset_x:offset_x+new_w])
    elif method == 'skip':
        return scipy.fftpack.fft2(scipy.fftpack.ifft2(I)[::2,::2])

def upsample2(I,shape=None,method='crop'):
    if method == 'crop':
        window_left = lambda width_big, width_small: np.where(scipy.fftpack.fftshift(scipy.fftpack.fftfreq(width_big)) == 0)[0].flatten()[0] - np.where(scipy.fftpack.fftshift(scipy.fftpack.fftfreq(width_small)) == 0)[0].flatten()[0]
        new_h = I.shape[0] * 2 if shape is None else shape[0]
        new_w = I.shape[1] * 2 if shape is None else shape[1]
        offset_y = window_left(new_h,I.shape[0])
        offset_x = window_left(new_w,I.shape[1])
        ret = np.zeros((new_h,new_w),dtype=np.complex)
        ret[offset_y:offset_y+I.shape[0],offset_x:offset_x+I.shape[1]] = scipy.fftpack.fftshift(I)
        return scipy.fftpack.ifftshift(ret)
    elif method == 'bilinear':
        ret = scipy.fftpack.ifft2(I)
        ret = np.insert(ret,range(1,I.shape[0]),(ret[:-1]+ret[1:])/2.,axis=0)
        ret = np.insert(ret,range(1,I.shape[1]),(ret[:,:-1]+ret[:,1:])/2.,axis=1)
        ret = np.pad(ret,((0,1),(0,1)), mode='edge')
        if shape is not None:
            return scipy.fftpack.fft2(ret[:shape[0],:shape[1]])
        else:
            return scipy.fftpack.fft2(ret)

def im2pyr(im,D,N,K):
    dft = scipy.fftpack.fft2
    idft = scipy.fftpack.ifft2

    I = dft(im)
    Rh = idft(apply_filter(I,lambda r, th: highpass_filter(r/2.,th)))
    P = []
    for d in range(D):
        P.append([ [ idft(apply_filter(I,lambda r, th: pyramid_filter(r,th,n,N,k,K))) for k in range(K) ] for n in range(N) ])
        I = downsample2(apply_filter(I,lowpass_filter))
    Rl = idft(I)
    return P, Rh, Rl

def pyr2im(P,Rh,Rl):
    dft = scipy.fftpack.fft2
    idft = scipy.fftpack.ifft2

    D = len(P)
    N = len(P[0])
    K = len(P[0][0])

    I = dft(Rl)
    for d in range(D-1,-1,-1):
        I = apply_filter(upsample2(I,shape=P[d][0][0].shape),lowpass_filter)
        for n in range(N):
            for k in range(K):
                J = apply_filter(dft(P[d][n][k]),lambda r, th: pyramid_filter(r,th,n,N,k,K))
                J_c = np.flip(scipy.fftpack.fftshift(np.array(np.conjugate(J),copy=True)),axis=(0,1))
                if J_c.shape[0] % 2 == 0:
                    J_c = np.roll(J_c,1,axis=0)
                    J_c[0,:] = 0.
                if J_c.shape[1] % 2 == 0:
                    J_c = np.roll(J_c,1,axis=1)
                    J_c[:,0] = 0.
                J_c = scipy.fftpack.ifftshift(J_c)
                I += J + J_c
    I += apply_filter(dft(Rh),lambda r, th: highpass_filter(r/2.,th))
    return idft(I)


## Debug code below
if __name__ == '__main__':

    import matplotlib.pyplot as plt

    disc = np.zeros((100,100),dtype=np.float32)
    for i in range(disc.shape[0]):
        for j in range(disc.shape[1]):
            if np.sqrt((i-disc.shape[0]//2)**2+(j-disc.shape[1]//2)**2) < 25:
                disc[i,j] = 1

    im = disc
    plt.imshow(disc)

    from PIL import Image
    from requests import get
    from io import BytesIO

    im = Image.open(BytesIO(get("https://rxian2.web.illinois.edu/cs445/proj1/a_im_in_colored2.jpg").content)).convert('LA')
    im = np.array(im,dtype=np.float32)[:,:,0]
    plt.imshow(im);plt.colorbar()

    P, Rh, Rl = im2pyr(im,2,2,4)

    re = np.real(pyr2im(P, Rh, Rl))
    plt.imshow(np.real(re));plt.colorbar()

    plt.imshow(np.real(re)-im);plt.colorbar()
