#include <stdlib.h>
#include <math.h>
__declspec(dllexport) int plate_run(int n,int nodes,const double*t,const double*qf,const double*qb,const double*gf,const double*gb,
 double k,double rc,double dx,double alpha,double eps,double ignition,double initial,double dt,double conv,
 double*surface,double*absorbed,double*crossing,double*residual){
 const double sigma=5.670374419e-8;double*T=malloc(nodes*sizeof(double)),*D=malloc(nodes*sizeof(double));
 if(!T||!D){free(T);free(D);return 1;}for(int j=0;j<nodes;j++)T[j]=initial+273.15;
 double energy0=rc*dx*(nodes-1)*(initial+273.15),netIntegral=0,cumulative=0;*crossing=NAN;surface[0]=initial;absorbed[0]=0;
 for(int i=1;i<n;i++){
  double maxT=300;for(int j=0;j<nodes;j++)maxT=fmax(maxT,T[j]);maxT=fmax(maxT,fmax(gf[i]+273.15,gb[i]+273.15));
  double deriv=4*eps*sigma*pow(maxT,3)+3*conv*pow(maxT,1./3.);
  double stable=.8/(2*k/(rc*dx*dx)+2*deriv/(rc*dx));int steps=(int)ceil((t[i]-t[i-1])/fmin(dt,stable));double step=(t[i]-t[i-1])/steps;
  for(int j=0;j<steps;j++){
   double f=(j+.5)/steps,front=((1-f)*qf[i-1]+f*qf[i])*1000,back=((1-f)*qb[i-1]+f*qb[i])*1000;
   double delta=(1-f)*gf[i-1]+f*gf[i]-(T[0]-273.15),delta_b=(1-f)*gb[i-1]+f*gb[i]-(T[nodes-1]-273.15);
   double net=alpha*front-eps*sigma*pow(T[0],4)+conv*pow(fabs(delta),1./3.)*delta;
   double netb=alpha*back-eps*sigma*pow(T[nodes-1],4)+conv*pow(fabs(delta_b),1./3.)*delta_b;
   for(int v=1;v<nodes-1;v++)D[v]=k/(rc*dx*dx)*(T[v-1]-2*T[v]+T[v+1]);
   D[0]=2*(net+k*(T[1]-T[0])/dx)/(rc*dx);D[nodes-1]=2*(netb+k*(T[nodes-2]-T[nodes-1])/dx)/(rc*dx);
   double before=T[0]-273.15;for(int v=0;v<nodes;v++)T[v]+=step*D[v];
   netIntegral+=step*(net+netb);cumulative+=step*alpha*front/1000;double now=T[0]-273.15;
   if(isnan(*crossing)&&before<ignition&&ignition<=now)*crossing=t[i-1]+(j+(ignition-before)/(now-before))*step;
  }
  surface[i]=T[0]-273.15;absorbed[i]=cumulative;
  for(int v=0;v<nodes;v++)if(!isfinite(T[v])||T[v]<=0){free(T);free(D);return 2;}
 }
 double sum=0;for(int v=0;v<nodes;v++)sum+=T[v];*residual=rc*dx*(sum-.5*T[0]-.5*T[nodes-1])-energy0-netIntegral;
 free(T);free(D);return fabs(*residual)>fmax(.01,fabs(netIntegral)*1e-9)?3:0;
}
